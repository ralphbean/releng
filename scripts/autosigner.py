#!/usr/bin/python -tt
# vim: fileencoding=utf8 foldmethod=marker
# SPDX-License-Identifier: GPL-2.0+
#{{{ License header: GPLv2+
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#}}}

import argparse
import collections
import fcntl
import getpass
import logging
import os
import Queue
import struct
import subprocess
import sys
import termios
import threading
import time
import traceback

log = logging.getLogger(__name__)

try:
    import simplejson as json
except ImportError:
    import json

import fedmsg
import fedmsg.meta

import sigulsign_unsigned as sigulsign

TOPIC_PREFIX = u"org.fedoraproject.prod."

TAG_INFO = {("f21", "f21-rebuild"): "fedora-21",
            ("f22", "f22-rebuild"): "fedora-22",
            }
secondary_instances = ["arm", "ppc", "s390"]

SigningEvent = collections.namedtuple("SigningEvent",
                                      "build_id, instance, key")


def terminal_size():
    def ioctl_GWINSZ(fd):
        try:
            placeholder = struct.pack('HHHH', 0, 0, 0, 0)
            winsize = fcntl.ioctl(fd, termios.TIOCGWINSZ, placeholder)
            return winsize
        except:
            return None
    winsize = ioctl_GWINSZ(0) or ioctl_GWINSZ(1) or ioctl_GWINSZ(2)
    rows, columns, xpixel, ypixel = struct.unpack('HHHH', winsize)
    return rows, columns


class TimeoutProcess(object):
    def __init__(self, command):
        self.command = command
        self.process = None

    def run(self, timeout=None, stdindata=None):
        def target():
            if stdindata:
                stdin = subprocess.PIPE
            else:
                stdin = None
            self.process = subprocess.Popen(self.command, stdin=stdin)
            self.process.communicate(stdindata)

        thread = threading.Thread(target=target)
        thread.start()

        thread.join(timeout)
        if thread.is_alive():
            self.process.kill()
        else:
            return self.process.returncode

        thread.join(1)
        if thread.is_alive():
            self.process.terminate()
        return None


def remove_certificate(msg):
    msg = dict(msg)
    msg["certificate"] = "REMOVED"
    msg["signature"] = "REMOVED"
    return msg


def signing_worker(queues, sigul_passwords, primary=True):
    kojihelpers = {}
    if primary:
        kojihelpers["primary"] = sigulsign.KojiHelper()
    else:
        for arch in secondary_instances:
            kojihelpers[arch] = sigulsign.KojiHelper(arch=arch)

    keys = list(queues)

    for key in keys:
        queue = queues[key]
        unsigned_rpms = []
        while not queue.empty():
            try:
                unsigned_rpms.append(queue.get(block=False))
            except Queue.Empty:
                break


class SingleSigner(object):
    def __init__(self, instance, key, password):
        self.instance = instance
        self.key = key
        self.key_id = sigulsign.KEYS
        self.password = password

        if self.instance == "primary":
            arch = None
            sigul_config = None
        else:
            arch = instance
            sigul_config = os.path.expanduser("~/.sigul/client-secondary.conf")

        self.kojihelper = sigulsign.KojiHelper(arch=arch)
        self.sigulhelper = sigulsign.SigulHelper(key, password, arch=arch,
                                                 config_file=sigul_config)

    def sign(self, build_id):
        def log_(level, msg, *args, **kwargs):
            log_infos = dict(build_id=build_id, instance=self.instance,
                             key=self.key)
            log_infos.update(kwargs)
            log_function = getattr(log, level)
            fmt = "{instance}/{build_id}/{key}: " + msg
            log_function(fmt.format(*args, **log_infos))

        log_("info", "Start processing using key {key}")
        rpminfo = self.kojihelper.get_rpms(build_id)
        if len(rpminfo) == 0:
            log_("error", "No RPMs found")
            return
        else:
            log_("info", "Found {count} RPMs", count=len(rpminfo))
        log_("debug", " RPMs: {rpminfo}", rpminfo=", ".join(list(rpminfo)))

        old_unsigned = {}
        unsigned = rpminfo
        while True:
            unsigned = self.kojihelper.get_unsigned_rpms(
                unsigned, self.sigulhelper.keyid)
            log_("info", "Found {unsigned_count}/{all_count} unsigned RPMs",
                 unsigned_count=len(unsigned), all_count=len(rpminfo))

            if len(unsigned) == 0:
                log_("info", "Everything signed")
                break
            elif list(unsigned) == list(old_unsigned):
                log_("critical", "Sigul did not sign any RPMS")
                break

            signed = [rpm for rpm in old_unsigned if rpm not in unsigned]
            if old_unsigned:
                log_("info", "Signed {count} RPMs", count=len(signed))

            old_unsigned = unsigned

            command = self.sigulhelper.build_sign_cmdline(list(unsigned))
            timeout_command = TimeoutProcess(command)
            timeout = 30 + len(unsigned) * 2
            if timeout > 300:
                timeout = 300

            log_("debug", "Running {cmd!r} with {timeout}s timeout",
                 cmd=command, timeout=timeout)
            sign_begin = time.time()
            ret = timeout_command.run(
                timeout=timeout, stdindata=self.sigulhelper.password + "\0")
            sign_end = time.time()
            sign_duration = sign_end - sign_begin
            duration_per_rpm = sign_duration / len(unsigned)
            log_("debug", "Sigul took {duration:.1f}s "
                "({duration_per_rpm:.2f}s per RPM)",
                duration=sign_duration, duration_per_rpm=duration_per_rpm)

            if ret is None:
                log_("warning", "Sigul timed out signing {count} RPMS after"
                     "{timeout}s", count=len(unsigned), timeout=timeout)
            else:
                log_("debug", "Sigul returned: {ret}", ret=ret)
        # FIXME write RPMs in koji


class AutoSigner(object):
    def __init__(self, sigul_passwords):
        self.sigul_passwords = sigul_passwords

    def sign(self, signing_event):
        sigul_password = self.sigul_passwords.get(signing_event.key)
        if not sigul_password:
            log.critical("Password missing for %s", signing_event)
            return

        signer = SingleSigner(signing_event.instance,
                              signing_event.key,
                              sigul_password)
        signer.sign(signing_event.build_id)


        # command = ["./sigulsign_unsigned.py", "-vv", "--batch-mode",
        #            "--sigul-batch-size=1"]
        # if signing_event.instance in secondary_instances:
        #     command.extend(
        #         [
        #             "--arch", signing_event.instance,
        #             "--sigul-config-file",
        #             os.path.expanduser("~/.sigul/client-secondary.conf")])
        # elif signing_event.instance != "primary":
        #     return -1

        # command.extend([signing_event.key, str(signing_event.build_id)])
        # log.info("Running", " ".join(command))
        # child = subprocess.Popen(command, stdin=subprocess.PIPE)
        # child.communicate(sigul_password + '\0')
        # ret = child.wait()
        # return ret


def parse_message(msg):
    if msg["topic"] == TOPIC_PREFIX + "buildsys.tag":
        for tags, key in TAG_INFO.items():
            if msg["msg"]["tag"] in tags:
                buildID = msg["msg"]["build_id"]
                instance = msg["msg"]["instance"]
                if instance in secondary_instances:
                    key += "-secondary"
                return SigningEvent(buildID, instance, key)
    return None


def ask_key_passwords():
    sigul_passwords = {}
    for tags, key in TAG_INFO.items():
        for k in ["", "-secondary"]:
            k = key + k
            sigul_password = getpass.getpass("Sigul {key} password: ".format(
                key=k))
            sigul_passwords[k] = sigul_password
    return sigul_passwords


def run(sigul_passwords):
    command = subprocess.Popen(["./autosigner.py", "--batch"],
                               stdin=subprocess.PIPE)
    command.communicate(input=json.dumps(sigul_passwords))


def setup_logging():
    log.setLevel(logging.DEBUG)
    console_logger = logging.StreamHandler()
    console_logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        '%(asctime)s: %(levelname)s: %(message)s',
    )
    formatter.converter = time.gmtime
    console_logger.setFormatter(formatter)
    log.addHandler(console_logger)


if __name__ == "__main__":
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument(
        "--batch", help="Read JSON information with password keys from stdin",
        action="store_true", default=False)
    args = argument_parser.parse_args()
    setup_logging()

    # Read in the config from /etc/fedmsg.d/
    config = fedmsg.config.load_config([], None)

    # Required for fedmsg.meta.msg2subtitle
    fedmsg.meta.make_processors(**config)

    # Disable a warning about not sending.  We know.  We only want to tail.
    config['mute'] = True

    # Disable timing out so that we can tail forever.  This is deprecated
    # and will disappear in future versions.
    config['timeout'] = 0

    if args.batch:
        sigul_passwords = json.load(sys.stdin)
    else:
        sigul_passwords = ask_key_passwords()
    auto_signer = AutoSigner(sigul_passwords)

    log.debug("Start processing messages")
    count = 0
    for name, endpoint, topic, msg in fedmsg.tail_messages(**config):
        try:
            count += 1
            short_topic = topic.replace(TOPIC_PREFIX, "")
            subtitle = fedmsg.meta.msg2subtitle(msg, **config)
            status = \
                u"\r\x1b[K{count} messages processed, last: {subtitle}".format(
                    count=count, subtitle=subtitle
                ).encode("utf-8")
            columns = terminal_size()[1]
            status = status[0:columns]
            sys.stderr.write(status)
            if topic.startswith(TOPIC_PREFIX + "buildsys.tag"):
                signing_event = parse_message(msg)
                if signing_event:
                    print ""
                    log.info("Got signing_event: %s", str(signing_event))
                    log.info(fedmsg.encoding.pretty_dumps(
                        remove_certificate(msg)))
                    auto_signer.sign(signing_event)
        except Exception, e:
            try:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                tb = traceback.format_exception(exc_type, exc_value,
                                                exc_traceback)
                log.error("Exception: %s", tb)
            except Exception, ee:
                log.error("Exception fallback %s", e)
