#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2014 Red Hat, Inc.
# SPDX-License-Identifier:      GPL-2.0
# Author: Dan Horák <dhorak@redhat.com>
#
# Find builds tagged in both fX-updates-testign and fX tags
# This can happen in the pre GA times when builds from bodhi go directly into
# the release, but they miss the untagging from updates-testing step
#


import sys
import koji
import argparse

# get parameters from command line
parser = argparse.ArgumentParser()
parser.add_argument("--arch", help="use when checking secondary arch koji")
parser.add_argument("tag", help="tag to check")
args = parser.parse_args()

if args.arch is None:
    print("working on primary koji")
    KOJIHUB = 'http://koji.fedoraproject.org/kojihub'
else:
    print("working on %s koji" % (args.arch))
    KOJIHUB = 'http://%s.koji.fedoraproject.org/kojihub' % (args.arch)

ga_tag = args.tag
testing_tag = args.tag + "-updates-testing"

kojisession = koji.ClientSession(KOJIHUB)

testing_nvrs = []
testing_dict = {}
ga_nvrs = []
cnt = 0

print("reading content of %s tag ..." % (testing_tag))
testing_builds = sorted(kojisession.listTagged(testing_tag), key = lambda pkg: pkg['package_name'])
for b in testing_builds:
    testing_nvrs.append(b['nvr'])
    testing_dict[b['nvr']] = b

print("reading content of %s tag ..." % (ga_tag))
ga_builds = sorted(kojisession.listTagged(ga_tag), key = lambda pkg: pkg['package_name'])
for b in ga_builds:
    ga_nvrs.append(b['nvr'])

print("testing=%s ga=%s" % (len(testing_builds), len(ga_builds)))

print("checking NVRs in both %s and %s tags ..." % (ga_tag, testing_tag))
for b in testing_nvrs:
    if b in ga_nvrs:
#	print("%s completed %s" % (b, testing_dict[b]['completion_time']))
	print("%s" % (b))
	cnt += 1

print("%s NVRs in both tags" % (cnt))
