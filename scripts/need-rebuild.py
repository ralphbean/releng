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
built = [] # raw list of built packages
unbuilt = [] # raw list of unbuilt packages

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
    kojisession.listBuilds(id, completeAfter=epoch)

# Get all the results
results = kojisession.multiCall()

# For each build, get it's request info
kojisession.multicall = True
for result in results:
    for oldbuild in result[0]:
        kojisession.getTaskInfo(oldbuild['task_id'],
                                request=True)

# For each request, compare to our target and populate the newbuild list.
requests = kojisession.multiCall()
for request in requests:
    tasktarget = request[0]['request'][1]
    taskpkg = request[0]['request'][0].rsplit('/')[-2]
    if tasktarget in buildtaglist:
        if not taskpkg in built:
            built.append(taskpkg)

# Loop through the results and build up a list of things to build
for pkg in pkgs:
    pkgname = pkg['package_name']
    if not pkgname in built:
        unbuilt.append(pkgname)
        if tobuild.has_key(pkg['owner_name']):
            tobuild[pkg['owner_name']].append(pkgname)
        else:
            tobuild[pkg['owner_name']] = [pkgname]

print "%s unbuilt packages:" % len(unbuilt)

print sorted(unbuilt)

# Print the results
for owner in sorted(tobuild.keys()):
    print "%s:" % owner
    for pkg in sorted(tobuild[owner]):
        print "    %s" % pkg
    print

