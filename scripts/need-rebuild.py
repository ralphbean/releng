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
unbuilt = [] # raw list of unbuilt packages
built = {} # raw list of built packages

# Create a koji session
kojisession = koji.ClientSession('https://koji.fedoraproject.org/kojihub')

kojisession.multicall = True
for tag in buildtaglist:
    kojisession.listTagged(tag, latest=True, inherit=True)

builds = kojisession.multiCall()

for [tag] in builds:
    for build in tag:
        if build['creation_time'] > epoch:
            built[build['package_name']] = build

kojisession.multicall = True
for [tag] in builds:
    for build in tag:
        if build['package_name'] in built.keys():
            continue
        if not build in unbuilt:
            unbuilt.append(build)
            kojisession.listPackages(tagID=buildtaglist[0],
                                     pkgID=build['package_id'],
                                     inherited=True)

pkginfo = kojisession.multiCall()
for [pkg] in pkginfo:
    tobuild.setdefault(pkg[0]['owner_name'], []).append(pkg[0]['package_name'])
        
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
