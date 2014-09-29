#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2013 Red Hat, Inc.
# SPDX-License-Identifier:      GPL-2.0
# Author: Dan Horák <dhorak@redhat.com>
#
# Find packages where latest and highest NVR are different in a tag.
# It can happen when bodhi pushes multiple builds of one package.
#

import argparse
import logging
log = logging.getLogger(__name__)
import subprocess

import koji
import rpm

# get parameters from command line
parser = argparse.ArgumentParser()
parser.add_argument("--arch", help="use when checking secondary arch koji")
parser.add_argument("--fix", help="retag the highest NVR to became the latest",
                    action="store_true")
parser.add_argument("--verbose", help="be verbose during processing",
                    action="store_true")
parser.add_argument("--debug", help="Enable debug output", action="store_true")
parser.add_argument("tag", help="tag to check")
parser.add_argument("package", nargs="*", help="packages to check")
args = parser.parse_args()

if args.debug:
    log.setLevel(logging.DEBUG)
log.debug("tag=%s arch=%s pkgs=%s", args.tag, args.arch, args.package)

if args.arch is None:
    KOJIHUB = 'http://koji.fedoraproject.org/kojihub'
else:
    KOJIHUB = 'http://%s.koji.fedoraproject.org/kojihub' % (args.arch)


def _rpmvercmp((e1, v1, r1), (e2, v2, r2)):
    """find out which build is newer"""
    if e1 == "None":
        e1 = "0"
    if e2 == "None":
        e2 = "0"
    rc = rpm.labelCompare((e1, v1, r1), (e2, v2, r2))
    if rc == 1:
        # first evr wins
        return 1
    elif rc == 0:
        # same evr
        return 0
    else:
        # second evr wins
        return -1


kojisession = koji.ClientSession(KOJIHUB)

if args.package == []:
    latest_builds = sorted(kojisession.listTagged(args.tag, latest=True),
                           key=lambda pkg: pkg['package_name'])
else:
    log.debug("pkgs=%s", args.package)
    latest_builds = []
    for p in args.package:
        latest_builds += kojisession.listTagged(args.tag, latest=True,
                                                package=p)

num = len(latest_builds)

log.debug("latest builds=%d", num)
log.debug(str(latest_builds))

for build in latest_builds:
    latest_evr = (str(build['epoch']), build['version'], build['release'])
    if args.verbose is True:
        print("pkg = %s" % build['package_name'])

    builds = kojisession.listTagged(args.tag, package=build['package_name'])
    for b in builds:
        evr = (str(b['epoch']), b['version'], b['release'])
        res = _rpmvercmp(latest_evr, evr)
        if res == -1:
            print("\tlatest is %s, but higher exists - %s" % (build['nvr'],
                                                              b['nvr']))
            if args.fix is True:
                cmd = ["koji", "untag-build", args.tag, b['nvr']]
                print("running: " + " ".join(cmd))
                subprocess.check_call(cmd)

                cmd = ["koji", "tag-build", args.tag, b['nvr']]
                print("running: " + " ".join(cmd))
                subprocess.check_call(cmd)
