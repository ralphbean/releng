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
newbuilds = {} # dict of packages that have a newer build attempt
tasks = {} # dict of new build task info

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
for build, [result] in zip(builds, results):
    if not build['package_name'] in pkgs:
        continue
    newbuilds[build['package_name']] = []
    for newbuild in result:
        newbuilds[build['package_name']].append(newbuild)
        kojisession.getTaskInfo(newbuild['task_id'],
                                request=True)

requests = kojisession.multiCall()

# Populate the task info dict
for [request] in requests:
    tasks[request['id']] = request

# Loop through the results and tag if necessary
kojisession.multicall = True
taglist = []
for build in builds:
    if not build['package_name'] in pkgs:
        print 'Skipping %s, blocked in %s' % (build['package_name'], target)
        continue
    for newbuild in newbuilds[build['package_name']]:
        # Scrape the task info out of the tasks dict from the newbuild task ID
        if tasks[newbuild['task_id']]['request'][1] == target:
            print 'Newer build found for %s.' % build['package_name']
            break
    else:
        print 'Tagging %s into %s' % (build['nvr'], target)
        taglist.append(build['nvr'])
        kojisession.tagBuildBypass(target, build)

print 'Tagging %s builds.' % len(taglist)
results = kojisession.multiCall()
