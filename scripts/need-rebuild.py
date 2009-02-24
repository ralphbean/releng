#!/usr/bin/python
#
# need-rebuild.py - A utility to discover packages that need a rebuild.
#
# Copyright (c) 2009 Red Hat
#
# Authors:
#     Jesse Keating <jkeating@redhat.com>
#

import koji
import os

# Set some variables
# Some of these could arguably be passed in as args.
buildtaglist = ['dist-f11', 'dist-f11-rebuild'] # tag(s) to check
epoch = '2009-02-23 18:31:07.000000' # rebuild anything not built after this date
tobuild = {} # dict of owners to lists of packages needing to be built

# Create a koji session
kojisession = koji.ClientSession('https://koji.fedoraproject.org/kojihub')

# Generate a list of packages to iterate over
pkgs = kojisession.listPackages(buildtaglist[0], inherited=True)

# reduce the list to those that are not blocked.
pkgs = [pkg for pkg in pkgs if not pkg['blocked']]

print "Checking %s packages..." % len(pkgs)

# Get builds for the packages
# Use multicall for quickness
kojisession.multicall = True

# Loop over each package
for pkg in pkgs:
    name = pkg['package_name']
    id = pkg['package_id']

    # Query to see if a build has already been attempted
    # this version requires newer koji:
    #  if  kojisession.listBuilds(id, createdAfter=epoch):
    # This version won't catch builds in flight
    kojisession.listBuilds(id, completeAfter=epoch)

# Get all the results
results = kojisession.multiCall()

# Loop through the results and build up a list of things to build
for pkg, result in zip(pkgs, results):
    newbuild = 0
    if result[0]:
        for build in result[0]:
            buildtarget = kojisession.getTaskInfo(build['task_id'],
                                       request=True)['request'][1]
            if buildtarget in buildtaglist:
                # We've already got an attempt made, skip.
                newbuild = True
                break

    if not newbuild:
        if tobuild.has_key(pkg['owner_name']):
            tobuild[pkg['owner_name']].append(pkg['package_name'])
        else:
            tobuild[pkg['owner_name']] = [pkg['package_name']]

# Print the results
for owner in sorted(tobuild.keys()):
    print "%s:" % owner
    for pkg in sorted(tobuild[owner]):
        print "    %s" % pkg
    print

