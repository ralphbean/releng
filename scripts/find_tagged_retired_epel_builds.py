#!/usr/bin/python -tt
# vim: fileencoding=utf8
# SPDX-License-Identifier: GPL-2.0+

import argparse
import getpass
import logging
import time


from autosigner import SubjectSMTPHandler
from block_retired import get_packages, run_koji


log = logging.getLogger(__name__)


# copied from block_retired.py
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
            "127.0.0.1", fedora_user, [fedora_user],
            "EPEL retired build monitor event")
        if debug:
            mail_logger.setLevel(logging.DEBUG)
        mail_logger.setFormatter(formatter)
        mail_logger.subject_prefix = "EPEL retired builld monitor: "
        log.addHandler(mail_logger)


def check_tag(tag, staging):
    buildtag = tag + "-build"
    _, blocked_in_tag = get_packages(tag)
    unblocked_in_buildtag, _ = get_packages(buildtag)

    for package in sorted(blocked_in_tag):
        if package in unblocked_in_buildtag:
            log.debug("Checking %s", package)
            cmd = ["latest-build", buildtag, package]
            process, latest_build, stderr = run_koji(cmd, staging=staging)
            if tag in latest_build and buildtag not in latest_build:
                yield dict(package=package, latest_build=latest_build)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Check if there are EPEL builds from retired packages "
        "still in the buildroot.")
    parser.add_argument("--debug", default=False, action="store_true")
    parser.add_argument("--tag", default=None,
                        help="Tag to check, default: all")
    parser.add_argument(
        "--staging", default=False, action="store_true",
        help="Talk to staging services (pkgdb), instead of production")
    args = parser.parse_args()

    setup_logging(args.debug)

    if args.tag is None:
        for tag in ["dist-5E-epel", "dist-6E-epel", "epel7"]:
            print("Tag: " + tag)
            problems = check_tag(tag, args.staging)
            for problem in problems:
                print problem["package"]
                log.debug(problem["latest_build"])
    else:
        problems = check_tag(args.tag, args.staging)
        for problem in problems:
            print problem["package"]
            log.debug(problem["latest_build"])
