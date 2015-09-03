#!/usr/bin/python -tt
# vim: fileencoding=utf8
# SPDX-License-Identifier: GPL-2.0+

import argparse
import datetime
import getpass
import logging
import os
import subprocess
import time

import koji
import pkgdb2client

from autosigner import SubjectSMTPHandler


log = logging.getLogger(__name__)
RETIRING_BRANCHES = ["el5", "el6", "epel7", "f23", "master"]
PROD_ONLY_BRANCHES = ["el5", "el6", "epel7", "master"]

PRODUCTION_PKGDB = "https://admin.fedoraproject.org/pkgdb"
STAGING_PKGDB = "https://admin.stg.fedoraproject.org/pkgdb"

PRODUCTION_KOJI = "https://koji.fedoraproject.org/kojihub"
STAGING_KOJI = "https://koji.stg.fedoraproject.org/kojihub"

# Should probably set these from a koji config file
SERVERCA = os.path.expanduser('~/.fedora-server-ca.cert')
CLIENTCA = os.path.expanduser('~/.fedora-upload-ca.cert')
CLIENTCERT = os.path.expanduser('~/.fedora.cert')


class ReleaseMapper(object):
    BRANCHNAME = 0
    KOJI_TAG = 1
    EPEL_BUILD_TAG = 2

    def __init__(self, staging=False):

        # git branchname, koji tag, epel build tag
        self.mapping = (
            ("master", "f24", ""),
            ("f23", "f23", ""),
            ("f22", "f22", ""),
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


def get_packages(tag, staging=False):
    """
    Get a list of all blocked and unblocked packages in a branch.
    """
    url = PRODUCTION_KOJI if not staging else STAGING_KOJI
    kojisession = koji.ClientSession(url)
    kojisession.ssl_login(CLIENTCERT, CLIENTCA, SERVERCA)
    pkglist = kojisession.listPackages(tagID=tag, inherited=True)
    blocked = []
    unblocked = []

    for p in pkglist:
        pkgname = p["package_name"]
        if p.get("blocked"):
            blocked.append(pkgname)
        else:
            unblocked.append(pkgname)

    return unblocked, blocked


def unblocked_packages(branch="master", staging=False):
    """
    Get a list of all unblocked pacakges in a branch.
    """
    mapper = ReleaseMapper(staging=staging)
    tag = mapper.koji_tag(branch)
    unblocked, _ = get_packages(tag, staging)
    return unblocked


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


def run_koji(koji_params, staging=False):
    url = PRODUCTION_KOJI if not staging else STAGING_KOJI
    koji_cmd = ["koji", "--server", url]
    cmd = koji_cmd + koji_params
    log.debug("Running: %s", " ".join(cmd))
    process = subprocess.Popen(cmd, stderr=subprocess.PIPE,
                               stdout=subprocess.PIPE)
    stdout, stderr = process.communicate()
    return process, stdout, stderr


def block_package(packages, branch="master", staging=False):
    if isinstance(packages, basestring):
        packages = [packages]

    if len(packages) == 0:
        return None

    mapper = ReleaseMapper(staging=staging)
    tag = mapper.koji_tag(branch)
    epel_build_tag = mapper.epel_build_tag(branch)

    errors = []

    def catch_koji_errors(cmd):
        process, stdout, stderr = run_koji(cmd, staging=staging)
        if process.returncode != 0:
            errors.append("{0} stdout: {1!r} stderr: {2!r}".format(cmd, stdout,
                                                                   stderr))

    # Untag builds first due to koji/mash bug:
    # https://fedorahosted.org/koji/ticket/299
    # FIXME: This introduces a theoretical race condition when a package is
    # built after all builds were untagged and before the package is blocked
    if epel_build_tag:
        cmd = ["untag-build", "--all", tag] + packages
        catch_koji_errors(cmd)

    cmd = ["block-pkg", tag] + packages
    catch_koji_errors(cmd)

    if epel_build_tag:
        cmd = ["unblock-pkg", epel_build_tag] + packages
        catch_koji_errors(cmd)

    return errors


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
        unblocked = []

        # Check which packages are included in a tag but not blocked, this
        # ensures that no packages not included in a tag are tried to be
        # blocked. Packages might not be in the rawhide tag if they are retired
        # too fast, e.g. because they are EPEL-only
        allunblocked = unblocked_packages(branch, staging)
        for pkg in retired:
            if pkg in allunblocked:
                unblocked.append(pkg)

        errors = block_package(unblocked, branch, staging=staging)
        # Block packages individually so that errors with one package does not
        # stop the other packages to be blocked
        if errors:
            for error in errors:
                log.error(error)
            for package in unblocked:
                errors = block_package(package, branch, staging=staging)
                log.info("Blocked %s on %s", package, branch)
                for error in errors:
                    log.error(error)


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
    parser = argparse.ArgumentParser(description="Block retired packages")
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
