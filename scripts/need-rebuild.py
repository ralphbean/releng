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
import operator

# Set some variables
# Some of these could arguably be passed in as args.
buildtag = 'dist-f11-rebuild' # tag(s) to check
target = 'dist-f11'
epoch = '2009-02-23 18:31:07.000000' # rebuild anything not built after this date
tobuild = {} # dict of owners to lists of packages needing to be built
unbuilt = [] # raw list of unbuilt packages
built = {} # raw list of built packages
newbuilds = {}
tasks = {}

# Create a koji session
kojisession = koji.ClientSession('https://koji.fedoraproject.org/kojihub')

# Generate a list of packages to iterate over
pkgs = kojisession.listPackages(target, inherited=True)

# reduce the list to those that are not blocked and sort by package name
pkgs = sorted([pkg for pkg in pkgs if not pkg['blocked']],
              key=operator.itemgetter('package_name'))

# Get completed builds since epoch
kojisession.multicall = True
for pkg in pkgs:
    kojisession.listBuilds(pkg['package_id'], state=1, createdAfter=epoch)

results = kojisession.multiCall()

# For each build, get it's request info
kojisession.multicall = True
for pkg, [result] in zip(pkgs, results):
    newbuilds[pkg['package_name']] = []
    for newbuild in result:
        newbuilds[pkg['package_name']].append(newbuild)
        kojisession.getTaskInfo(newbuild['task_id'],
                                request=True)

requests = kojisession.multiCall()

# Populate the task info dict
for request in requests:
    if len(request) > 1:
        continue
    tasks[request[0]['id']] = request[0]

for pkg in pkgs:
    for newbuild in newbuilds[pkg['package_name']]:
        # Scrape the task info out of the tasks dict from the newbuild task ID
        try:
            if tasks[newbuild['task_id']]['request'][1] in [target, buildtag]:
                break
        except:
            pass
    else:
        tobuild.setdefault(pkg['owner_name'], []).append(pkg['package_name'])
        unbuilt.append(pkg)

print '<html>'
print '<body>'
print "%s unbuilt packages:<p>" % len(unbuilt)

# Print the results
print '<dl>'
print '<style type="text/css"> dt { margin-top: 1em } </style>'
for owner in sorted(tobuild.keys()):
    print '<dt>%s (%s):</dt>' % (owner, len(tobuild[owner]))
    for pkg in sorted(tobuild[owner]):
        print '<dd><a href="http://koji.fedoraproject.org/koji/packageinfo?packageID=%s">%s</a></dd>' % (pkg, pkg)
    print '</dl>'
print '</body>'
print '</html>'
