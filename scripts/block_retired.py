#!/usr/bin/python -tt
# vim: fileencoding=utf8
# SPDX-License-Identifier: GPL-2.0+

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
PROD_ONLY_BRANCHES = ["el5", "el6", "epel7", "master"]

PRODUCTION_PKGDB = "https://admin.fedoraproject.org/pkgdb"
STAGING_PKGDB = "https://admin.stg.fedoraproject.org/pkgdb"

PRODUCTION_KOJI = "https://koji.fedoraproject.org/kojihub"
STAGING_KOJI = "https://koji.stg.fedoraproject.org/kojihub"


class ReleaseMapper(object):
    BRANCHNAME = 0
    KOJI_TAG = 1
    EPEL_BUILD_TAG = 2

    def __init__(self, staging=False):

        # git branchname, koji tag, pkgdb version
        self.mapping = (
            ("master", "f22", ""),
            ("f21", "f21", ""),
            ("f20", "f20", ""),
            ("f19", "f19", ""),
            ("f18", "f18", ""),
        )
        if not staging:
            self.mapping = self.mapping + (
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


def blocked_packages(branch="master", staging=False):
    mapper = ReleaseMapper(staging=staging)
    tag = mapper.koji_tag(branch)
    url = PRODUCTION_KOJI if not staging else STAGING_KOJI
    kojisession = koji.ClientSession(url)
    pkglist = kojisession.listPackages(tagID=tag, inherited=True)
    blocked = [p["package_name"] for p in pkglist if p.get("blocked")]
    return blocked


def get_retired_packages(branch="master", staging=False):
    url = PRODUCTION_PKGDB if not staging else STAGING_PKGDB
    pkgdb = pkgdb2client.PkgDB(url)

    try:
        retiredresponse = pkgdb.get_packages(
            "", branches=branch, page="all", status="Retired")
    except pkgdb2client.PkgDBException as e:
        if "No packages found for these parameters" not in str(e):
            raise
        return []

    retiredinfo = retiredresponse["packages"]
    retiredpkgs = [p["name"] for p in retiredinfo]
    return retiredpkgs


def pkgdb_retirement_status(package, branch="master", staging=False):
    """ Returns retirement info for `package` in `branch`

    :returns: dict: retired: True - if retired, False if not, None if
    there was an error, status_change: last status change as datetime object
    """

    url = PRODUCTION_PKGDB if not staging else STAGING_PKGDB
    pkgdb = pkgdb2client.PkgDB(url)
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


def block_package(packages, branch="master", staging=False):
    if isinstance(packages, basestring):
        packages = [packages]

    if len(packages) == 0:
        return None

    def run_koji(koji_params):
        url = PRODUCTION_KOJI if not staging else STAGING_KOJI
        koji_cmd = ["koji", "--server", url]
        cmd = koji_cmd + koji_params
        log.debug("Running: %s", " ".join(cmd))
        return subprocess.check_call(cmd)

    mapper = ReleaseMapper(staging=staging)
    tag = mapper.koji_tag(branch)
    run_koji(["block-pkg", tag] + packages)

    epel_build_tag = mapper.epel_build_tag(branch)

    if epel_build_tag:
        run_koji(["untag-build", "--all", tag] + packages)
        run_koji(["unblock-pkg", epel_build_tag] + packages)


def handle_message(message, retiring_branches=RETIRING_BRANCHES,
                   staging=False):
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

    pkgdbinfo = pkgdb_retirement_status(package, branch, staging)

    if pkgdbinfo["retired"] is not True:
        log.error("Processing '%s', package '%s' not retired",
                  msg_id, package)

    log.debug("'%s' retired on '%s'", package, pkgdbinfo["status_change"])
    return block_package(package, branch, staging=staging)


def block_all_retired(branches=RETIRING_BRANCHES, staging=False):
    for branch in branches:
        log.debug("Processing branch %s", branch)
        if staging and branch in PROD_ONLY_BRANCHES:
            log.warning('%s not handled in staging..' % branch)
            continue
        retired = get_retired_packages(branch, staging)
        blocked = blocked_packages(branch, staging)

        unblocked = []
        for pkg in retired:
            if pkg not in blocked:
                unblocked.append(pkg)

        if unblocked:
            log.info("Blocked packages %s on %s", unblocked, branch)
            block_package(unblocked, branch, staging=staging)


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
    parser.add_argument(
        "--staging", default=False, action="store_true",
        help="Talk to staging services (pkgdb), instead of production")
    args = parser.parse_args()

    setup_logging(args.debug)

    if not args.packages:
        block_all_retired(staging=args.staging)
    else:
        block_package(args.packages, args.branch, staging=args.staging)
