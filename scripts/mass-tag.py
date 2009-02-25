#!/usr/bin/python
#
# mass-tag.py - A utility to tag rebuilt packages.
#
# Copyright (c) 2009 Red Hat
#
# Authors:
#     Jesse Keating <jkeating@redhat.com>
#

import koji
import os
import operator

# Set some variables
# Some of these could arguably be passed in as args.
target = 'dist-f11' # tag to tag into
holdingtag = 'dist-f11-rebuild' # tag holding the rebuilds
newbuilds = [] # list of packages that have a newer build attempt

# Create a koji session
kojisession = koji.ClientSession('https://koji.fedoraproject.org/kojihub')

# Log into koji
clientcert = os.path.expanduser('~/.fedora.cert')
clientca = os.path.expanduser('~/.fedora-upload-ca.cert')
serverca = os.path.expanduser('~/.fedora-server-ca.cert')
kojisession.ssl_login(clientcert, clientca, serverca)

# Generate a list of builds to iterate over, sorted by package name
builds = sorted(kojisession.listTagged(holdingtag, latest=True),
                key=operator.itemgetter('package_name'))

# Generate a list of packages in the target, reduced by not blocked.
pkgs = kojisession.listPackages(target, inherited=True)
pkgs = [pkg['package_name'] for pkg in pkgs if not pkg['blocked']]

print 'Checking %s builds...' % len(builds)

# Use multicall
kojisession.multicall = True

# Loop over each build
for build in builds:
    id = build['package_id']
    builddate = build['creation_time']

    # Query to see if a build has already been attempted
    kojisession.listBuilds(id, createdAfter=builddate)

# Get the results
results = kojisession.multiCall()

# For each build, get it's request info
kojisession.multicall = True
for build, result in zip(builds, results):
    if not build['package_name'] in pkgs:
        print 'Skipping %s, blocked in %s' % (pkg['package_name'], target)
        continue
    for oldbuild in result[0]:
        kojisession.getTaskInfo(oldbuild['task_id'],
                                request=True)

# For each request, compare to our target and populate the newbuild list.
requests = kojisession.multiCall()
for request in requests:
    tasktarget = request[0]['request'][1]
    taskpkg = request[0]['request'][0].rsplit('/')[-2]
    if tasktarget == target:
        if not taskpkg in newbuilds:
            newbuilds.append(taskpkg)

# Loop through the results and tag if necessary
kojisession.multicall = True
for build, result in zip(builds, results):
    if not build['package_name'] in pkgs:
        continue
    if build['package_name'] in newbuilds:
        print 'Newer build found for %s.' % build['package_name']
    else:
        print 'Tagging %s into %s' % (build['nvr'], target)
        kojisession.tagBuildBypass(target, build)

results = kojisession.multiCall()
