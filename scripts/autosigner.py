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
import fcntl
import getpass
import logging
import logging.handlers
import os
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


class AutosignerSMTPHandler(logging.handlers.SMTPHandler):
    def getSubject(self, record):
        first_line = record.message.split("\n")[0]
        fmt = "Autosigner: {0.levelname}: {first_line}"

        return fmt.format(record, first_line=first_line)


class SigningTask(object):
    def __init__(self, build_id, instance, key, msg_id=None):
        self.build_id = build_id
        self.instance = str(instance)
        self.key = key
        self.unsigned = None
        self.error_count = 0
        self.last_attempt = 0
        self.created = time.time()
        self.msg_id = msg_id

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        fmt = "SigningTask({0.build_id!r}, {0.instance!r}, {0.key!r}"
        if self.msg_id:
            fmt += ", msg_id={0.msg_id!r}"

        fmt += ")"
        return fmt.format(self)


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

    def sign(self, build_id=None, signing_task=None):
        if not signing_task and build_id:
            signing_task = SigningTask(build_id, self.instance, self.key)

        def log_(level, msg, *args, **kwargs):
            log_infos = dict(build_id=signing_task.build_id,
                             instance=self.instance, key=self.key)
            log_infos.update(kwargs)
            log_function = getattr(log, level)
            fmt = "{instance}/{build_id}/{key}: " + msg
            log_function(fmt.format(*args, **log_infos))

        log_("debug", "Start processing using key {key}")

        rpminfo = self.kojihelper.get_rpms(signing_task.build_id)
        if len(rpminfo) == 0:
            log_("error", "No RPMs found")
            return
        else:
            log_("debug", "Found {count} RPMs", count=len(rpminfo))

        log_("debug", " RPMs: {rpminfo}", rpminfo=", ".join(list(rpminfo)))

        old_unsigned = {}
        unsigned = rpminfo
        while True:
            unsigned = self.kojihelper.get_unsigned_rpms(
                unsigned, self.sigulhelper.keyid)
            log_("debug", "Found {unsigned_count}/{all_count} unsigned RPMs",
                 unsigned_count=len(unsigned), all_count=len(rpminfo))

            if len(unsigned) == 0:
                log_("debug", "Everything signed")
                break

            signed = [rpm for rpm in old_unsigned if rpm not in unsigned]
            if old_unsigned:
                log_("debug", "Signed {count} RPMs", count=len(signed))

                if len(signed) == 0:
                    log_("critical", "Sigul did not sign any RPMS")
                    break

            old_unsigned = unsigned

            command = self.sigulhelper.build_sign_cmdline(list(unsigned))
            timeout_command = TimeoutProcess(command)
            timeout = 60 + len(unsigned)

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
                log_("warning", "Sigul timed out signing {count} RPMS after "
                     "{timeout}s", count=len(unsigned), timeout=timeout)
            else:
                log_("debug", "Sigul returned: {ret}", ret=ret)

        signed = [rpm for rpm in rpminfo if rpm not in unsigned]
        log_("debug", "Writing signed RPMS: {rpms}",
             rpms=", ".join(list(signed)))
        errors = self.kojihelper.write_signed_rpms(signed,
                                                   self.sigulhelper.keyid)
        if errors:
            log_("error", "Errors writing RPMS: {errors}", errors=errors)

        if errors or unsigned:
            log_("warning", "Not completed, write errors: {errors}, "
                 "unsigned: {unsigned}", errors=errors, unsigned=unsigned)
        else:
            log_("info", "Completed: {rpms}", rpms=", ".join(
                sorted(list(rpminfo))))
        signing_task.unsigned = unsigned
        return signing_task


class AutoSigner(object):
    def __init__(self, sigul_passwords):
        self.sigul_passwords = sigul_passwords
        self.incomplete = []
        self.signers = {}
        self.last_retry_attempt = 0

    def sign(self, signing_task):
        sigul_password = self.sigul_passwords.get(signing_task.key)
        if not sigul_password:
            log.critical("Password missing for %s", signing_task)
            return

        signer_id = "{0.instance}_{0.key}".format(signing_task)

        # Do not use self.signers.setdefault() to avoid creating the
        # SingleSigner if it is not needed
        if signer_id in self.signers:
            signer = self.signers[signer_id]
        else:
            signer = SingleSigner(signing_task.instance, signing_task.key,
                                  sigul_password)
            self.signers[signer_id] = signer

        signing_task = signer.sign(signing_task=signing_task)
        if signing_task.unsigned:
            signing_task.error_count += 1
            signing_task.last_attempt = time.time()
            self.incomplete.append(signing_task)
            return False
        else:
            return True

    def retry(self, force_check=False):
        now = time.time()
        # only retry once every 5 minutes
        if not force_check and now < (self.last_retry_attempt + 300):
            return None

        if len(self.incomplete) < 10:
            waiting_time = 300
        else:
            waiting_time = 1800

        incomplete = self.incomplete
        self.incomplete = []
        while incomplete:
            signing_task = incomplete.pop(0)
            if force_check or \
                    signing_task.last_attempt > (now + waiting_time):
                log.debug("Retrying %r", signing_task)
                signing_success = self.sign(signing_task)
                if not force_check and not signing_success:
                    while incomplete:
                        self.incomplete.insert(0, incomplete.pop(0))
            else:
                self.incomplete.append(signing_task)
        self.last_retry_attempt = time.time()

        # command = ["./sigulsign_unsigned.py", "-vv", "--batch-mode",
        #            "--sigul-batch-size=1"]
        # if signing_task.instance in secondary_instances:
        #     command.extend(
        #         [
        #             "--arch", signing_task.instance,
        #             "--sigul-config-file",
        #             os.path.expanduser("~/.sigul/client-secondary.conf")])
        # elif signing_task.instance != "primary":
        #     return -1
        #
        # command.extend([signing_task.key, str(signing_task.build_id)])
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
                return SigningTask(buildID, instance, key,
                                   msg_id=msg["msg_id"])
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

    formatter = logging.Formatter(
        '%(asctime)s: %(levelname)s: %(message)s',
    )
    # Log in UTC
    formatter.converter = time.gmtime

    console_logger = logging.StreamHandler()
    console_logger.setLevel(logging.DEBUG)
    console_logger.setFormatter(formatter)
    log.addHandler(console_logger)

    # FIXME: Make this a config option
    fedora_user = getpass.getuser()
    mail_logger = AutosignerSMTPHandler(
        "127.0.0.1", fedora_user, [fedora_user], "Autosigner log event")
    mail_logger.setLevel(logging.WARNING)
    mail_logger.setFormatter(formatter)
    log.addHandler(mail_logger)

    log_basedir = os.path.expanduser("~/autosigner-logs")
    try:
        os.makedirs(log_basedir, 0700)
    except OSError, e:
        # File exists
        if e.errno == 17:
            pass
        else:
            raise

    debug_logfilename = os.path.join(log_basedir, "debug.log")
    debug_logger = logging.handlers.TimedRotatingFileHandler(
        debug_logfilename, when="midnight", backupCount=14, utc=True)
    debug_logger.setFormatter(formatter)
    debug_logger.setLevel(logging.DEBUG)
    log.addHandler(debug_logger)

    info_logfilename = os.path.join(log_basedir, "info.log")
    info_logger = logging.handlers.TimedRotatingFileHandler(
        info_logfilename, when="midnight", backupCount=14, utc=True)
    info_logger.setFormatter(formatter)
    info_logger.setLevel(logging.INFO)
    log.addHandler(info_logger)


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

    log.info("Start processing messages for %r", TAG_INFO)
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
                signing_task = parse_message(msg)
                if signing_task:
                    print ""
                    log.debug("NEW: %s", str(signing_task))
                    log.debug("Processing message: %s",
                              fedmsg.encoding.pretty_dumps(
                                  remove_certificate(msg)))
                    if auto_signer.sign(signing_task):
                        auto_signer.retry(force_check=True)
            else:
                auto_signer.retry()
        except Exception, e:
            try:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                tb = traceback.format_exception(exc_type, exc_value,
                                                exc_traceback)
                log.error("Exception: %s", "".join(tb))
            except Exception, ee:
                log.error("Exception fallback %s", e)
