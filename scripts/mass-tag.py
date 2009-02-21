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
totag = []

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

print 'Checking %s builds...' % len(builds)

# Use multicall
kojisession.multicall = True

# Loop over each build
for build in builds:
    id = build['package_id']
    builddate = build['creation_time']

    # Query to see if a build has already been attempted
    # this version requires newer koji:
    # kojisession.listBuilds(id, createdAfter=builddate):
    # This version won't catch builds in flight
    kojisession.listBuilds(id, completeAfter=builddate)

# Get the results
results = kojisession.multiCall()

# Loop through the results and tag if necessary
for build, result in zip(builds, results):
    newerbuild = False
    for oldbuild in result[0]:
        if kojisession.getTaskInfo(oldbuild['task_id'],
                                   request=True)['request'][1] == target:
            newerbuild = True
            break
    if newerbuild:
        print 'Newer build found for %s.' % build['package_name']
    else:
        totag.append(build)

# use multicall again
kojisession.multicall = True

# Tag all the things needing to be tagged
for build in totag:
    print 'Tagging %s into %s' % (build['nvr'], target)
    kojisession.tagBuildBypass(target, build)

results = kojisession.multiCall()
