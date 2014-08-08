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
import datetime
import getpass
import subprocess
import sys
import traceback

import fedmsg
import fedmsg.meta

TOPIC_PREFIX = u"org.fedoraproject.prod."

TAG_INFO = {("f21", "f21-rebuild"): "fedora-21",
            ("f22", "f22-rebuild"): "fedora-22",
            }


def print_info(*msg):
    now = datetime.datetime.utcnow()
    timestr = str(now) + "  0000"
    print timestr, "INFO:", " ".join(msg)


def remove_certificate(msg):
    msg = dict(msg)
    msg["certificate"] = "REMOVED"
    msg["signature"] = "REMOVED"
    return msg


def sign_build(buildID, key, password, instance="primary"):
    if instance == "primary":
        command = ["./sigulsign_unsigned.py", "-vv", "--batch-mode",
                   "--sigul-batch-size=1", key, str(buildID)]
    else:
        return -1
    print_info("Running", " ".join(command))
    child = subprocess.Popen(command, stdin=subprocess.PIPE)
    child.communicate(password + '\0')
    ret = child.wait()
    return ret


def extract_buildID(msg):
    if msg["topic"] == TOPIC_PREFIX + "buildsys.tag":
        for tags, key in TAG_INFO.items():
            if msg["msg"]["tag"] in tags:
                buildID = msg["msg"]["build_id"]
                instance = msg["msg"]["instance"]
            return buildID, instance, key
    return None, None, None


if __name__ == "__main__":
    # Read in the config from /etc/fedmsg.d/
    config = fedmsg.config.load_config([], None)

    # Required for fedmsg.meta.msg2subtitle
    fedmsg.meta.make_processors(**config)

    # Disable a warning about not sending.  We know.  We only want to tail.
    config['mute'] = True

    # Disable timing out so that we can tail forever.  This is deprecated
    # and will disappear in future versions.
    config['timeout'] = 0

    sigul_passwords = {}
    for tags, key in TAG_INFO.items():
        for k in ["", "-secondary"]:
            k = key + k
            sigul_password = getpass.getpass("Sigul {key} password: ".format(key=k))
            sigul_passwords[key] = sigul_password

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
            sys.stderr.write(status)
            if topic.startswith(TOPIC_PREFIX + "buildsys.tag"):
                buildID, instance, key = extract_buildID(msg)
                if buildID:
                    print ""
                    print_info("Got buildID", str(buildID))
                    print_info(fedmsg.encoding.pretty_dumps(
                        remove_certificate(msg)))
                    sign_build(buildID, key, sigul_password, instance=instance)
        except Exception, e:
            try:
                print "EXCEPTION", e
                traceback.print_last()
            except Exception, ee:
                print "EXCEPTION fallback", ee
