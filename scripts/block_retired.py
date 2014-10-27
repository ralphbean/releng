#!/usr/bin/python -tt
# vim: fileencoding=utf8 foldmethod=marker
# SPDX-License-Identifier: GPL-2.0+
# {{{ License header: GPLv2+
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
# }}}

import argparse
import datetime
import getpass
import logging
import subprocess
import time

import koji
import pkgdb2client

from autosigner import SubjectSMTPHandler


log = logging.getLogger(__name__)
RETIRING_BRANCHES = ["el5", "el6", "epel7", "f21", "master"]


class ReleaseMapper(object):
    BRANCHNAME = 0
    KOJI_TAG = 1
    EPEL_BUILD_TAG = 2

    def __init__(self):

        # git branchname, koji tag, pkgdb version
        self.mapping = (
            ("master", "f22", ""),
            ("f21", "f21", ""),
            ("f20", "f20", ""),
            ("f19", "f19", ""),
            ("f18", "f18", ""),
            ("epel7", "epel7", "epel7-build"),
            ("el6", "dist-6E-epel", "dist-6E-epel-build"),
            ("el5", "dist-5E-epel", "dist-5E-epel-build"),
        )

    def branchname(self, key=""):
        return self.lookup(key, self.BRANCHNAME)

    def koji_tag(self, key=""):
        return self.lookup(key, self.KOJI_TAG)

    def epel_build_tag(self, key=""):
        return self.lookup(key, self.EPEL_BUILD_TAG)

    def lookup(self, key, column):
        if key:
            key = key.lower()
            for row in self.mapping:
                for c in row:
                    if c.lower() == key:
                        return row[column]
        else:
            return [row[column] for row in self.mapping]
        return None


def blocked_packages(branch="master"):
    mapper = ReleaseMapper()
    tag = mapper.koji_tag(branch)
    kojisession = koji.ClientSession('https://koji.fedoraproject.org/kojihub')
    pkglist = kojisession.listPackages(tagID=tag, inherited=True)
    blocked = [p["package_name"] for p in pkglist if p["blocked"]]
    return blocked


def get_retired_packages(branch="master"):
    pkgdb = pkgdb2client.PkgDB()
    retiredresponse = pkgdb.get_packages(
        "", branches=branch, page="all", status="Retired")
    retiredinfo = retiredresponse["packages"]
    retiredpkgs = [p["name"] for p in retiredinfo]
    return retiredpkgs


def pkgdb_retirement_status(package, branch="master"):
    """ Returns retirement info for `package` in `branch`

    :returns: dict: retired: True - if retired, False if not, None if
    there was an error, status_change: last status change as datetime object
    """

    pkgdb = pkgdb2client.PkgDB()
    retired = None
    status_change = None
    try:
        pkgdbresult = pkgdb.get_package(package, branches=branch)
        if pkgdbresult["output"] == "ok":
            for pkginfo in pkgdbresult["packages"]:
                if pkginfo["package"]["name"] == package:
                    if pkginfo["status"] == "Retired":
                        retired = True
                    else:
                        retired = False
                    status_change = datetime.datetime.fromtimestamp(
                        pkginfo["status_change"])
                    break
    except:
        pass

    return dict(retired=retired, status_change=status_change)


def get_retirement_info(message):
    """ Check whether a message is a retire message.

    :param message: Message to check
    :returns: (str, str, bool) or (None, None, None): package name and
    branch the package was retired on, bool: True: package was retired, False:
        package was unretired

    """
    if message['topic'] == \
            u'org.fedoraproject.prod.pkgdb.package.update.status':
        msg = message['msg']
        pkgname = msg['package_listing']['package']['name']
        branch = msg['package_listing']['collection']['branchname']
        res = dict(name=pkgname, branch=branch)
        if msg["prev_status"] != "Retired" and msg["status"] == "Retired":
            res["retired"] = True
        elif msg["prev_status"] == "Retired" and \
                msg["status"] != "Retired":
            res["retired"] = False
        return res
    return None


def block_package(packages, branch="master"):
    if isinstance(packages, basestring):
        packages = [packages]

    if len(packages) == 0:
        return None

    mapper = ReleaseMapper()
    tag = mapper.koji_tag(branch)
    cmd = ["koji", "block-pkg", tag] + packages
    log.debug("Running: %s", " ".join(cmd))
    subprocess.check_call(cmd)

    epel_build_tag = mapper.epel_build_tag(branch)

    if epel_build_tag:
        cmd = ["koji", "untag-build", "--all", tag] + packages
        log.debug("Running: %s", " ".join(cmd))
        subprocess.check_call(cmd)

        cmd = ["koji", "unblock-pkg", epel_build_tag] + packages
        log.debug("Running: %s", " ".join(cmd))
        subprocess.check_call(cmd)


def handle_message(message, retiring_branches=RETIRING_BRANCHES):
    messageinfo = get_retirement_info(message)
    msg_id = message["msg_id"]
    if messageinfo is None:
        return None

    if messageinfo["retired"] is False:
        return False

    branch = messageinfo["branch"]
    if branch not in retiring_branches:
        log.error("Message '%s' for the wrong branch '%s'", msg_id,
                  branch)
        return None

    package = messageinfo["name"]

    pkgdbinfo = pkgdb_retirement_status(package, branch)

    if pkgdbinfo["retired"] is not True:
        log.error("Processing '%s', package '%s' not retired",
                  msg_id, package)

    log.debug("'%s' retired on '%s'", package, pkgdbinfo["status_change"])
    return block_package(package, branch)


def block_all_retired(branches=RETIRING_BRANCHES):
    for branch in branches:
        log.debug("Processing branch %s", branch)
        retired = get_retired_packages(branch)
        blocked = blocked_packages(branch)

        unblocked = []
        for pkg in retired:
            if pkg not in blocked:
                unblocked.append(pkg)

        if unblocked:
            log.info("Blocked packages %s on %s", unblocked, branch)
            block_package(unblocked, branch)


def setup_logging(debug=False, mail=False):
    if debug:
        log.setLevel(logging.DEBUG)
    else:
        log.setLevel(logging.INFO)

    formatter = logging.Formatter(
        '%(asctime)s: %(levelname)s: %(message)s',
    )
    # Log in UTC
    formatter.converter = time.gmtime

    console_logger = logging.StreamHandler()
    if debug:
        console_logger.setLevel(logging.DEBUG)
    else:
        console_logger.setLevel(logging.INFO)
    console_logger.setFormatter(formatter)
    log.addHandler(console_logger)

    if mail:
        # FIXME: Make this a config option
        fedora_user = getpass.getuser()
        mail_logger = SubjectSMTPHandler(
            "127.0.0.1", fedora_user, [fedora_user], "block_retired event")
        if debug:
            mail_logger.setLevel(logging.DEBUG)
        mail_logger.setFormatter(formatter)
        mail_logger.subject_prefix = "Package Blocker: "
        log.addHandler(mail_logger)


if __name__ == "__main__":
    parser = argparse.ArgumentParser("Block retired packages")
    parser.add_argument("--debug", default=False, action="store_true")
    parser.add_argument("packages", nargs="*", metavar="package",
                        help="Packages to block, default all retired packages")
    parser.add_argument(
        "--branch", default="master",
        help="Branch to retire specified packages on, default: %(default)s")
    args = parser.parse_args()

    setup_logging(args.debug)

    if not args.packages:
        block_all_retired()
    else:
        block_package(args.packages, args.branch)
