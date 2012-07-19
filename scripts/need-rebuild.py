#!/usr/bin/python
#
# need-rebuild.py - A utility to discover packages that need a rebuild.
#
# Copyright (c) 2009 Red Hat
#
# Authors:
#     Jesse Keating <jkeating@redhat.com>
#     Milos Jakubicek <xjakub@fi.muni.cz>
#

import koji
import os
import operator
import datetime
import sys

# Set some variables
# Some of these could arguably be passed in as args.
buildtag = 'f18-rebuild' # tag(s) to check
target = 'f18'
updates = 'f18-updates-candidate'
rawhide = 'f18' # Change to dist-f13 after we branch
epoch = '2012-07-17 14:18:03.000000' # rebuild anything not built after this date
tobuild = {} # dict of owners to lists of packages needing to be built
unbuilt = [] # raw list of unbuilt packages
newbuilds = {}
tasks = {}
# List of Kojihubs to be searched
kojihubs = [
'http://koji.fedoraproject.org/kojihub',
'http://sparc.koji.fedoraproject.org/kojihub',
'http://s390.koji.fedoraproject.org/kojihub',
'http://ppc.koji.fedoraproject.org/kojihub',
'http://arm.koji.fedoraproject.org/kojihub',
]

def needRebuild(kojihub):

    # Create a koji session
    kojisession = koji.ClientSession(kojihub)

    # Generate a list of packages to iterate over
    try:
        pkgs = kojisession.listPackages(target, inherited=True)
    except:
        print >> sys.stderr, "Failed to get the packages list from koji: %s (skipping)" % kojihub
        return -1
    print "%s<br/>" % kojihub

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

    try:
        requests = kojisession.multiCall()
    except:
        print >> sys.stderr, "Failed to get the build request information: %s (skipping)" % kojihub
        return -1


    # Populate the task info dict
    for request in requests:
        if len(request) > 1:
            continue
        tasks[request[0]['id']] = request[0]

    unbuiltnew = []
    for pkg in pkgs:
        for newbuild in newbuilds[pkg['package_name']]:
            # Scrape the task info out of the tasks dict from the newbuild task ID
            try:
                if tasks[newbuild['task_id']]['request'][1] in [target, buildtag, updates, rawhide]:
                    break
            except:
                pass
        else:
            tobuild.setdefault(pkg['owner_name'], set()).add(pkg['package_name'])
            unbuiltnew.append(pkg['package_name'])
    return set(unbuiltnew)

now = datetime.datetime.now()
now_str = "%s UTC" % str(now.utcnow())
print '<html><head>'
print '<title>Packages that need to be rebuild as of %s</title>' % now_str
print '<style type="text/css"> dt { margin-top: 1em } </style>'
print '</head><body>'
print "<p>Last run: %s</p>" % now_str
print "<p>Included build tags: %s</p>" % [target, buildtag, updates, rawhide]
print "<p>Included Koji instances:<br/>"

# Go through all Kojis to get unbuilt packages
for kojihub in kojihubs:
    unbuiltnew = needRebuild(kojihub)
    if unbuiltnew == -1:
        continue
    if len(unbuilt) == 0:
        unbuilt = unbuiltnew
    else:
        unbuilt = unbuilt & unbuiltnew
print "</p>"

# Update the maintainer-package list
for owner in tobuild.keys():
    for pkg in tobuild[owner].copy():
        if pkg not in unbuilt:
            tobuild[owner].remove(pkg)
    if len(tobuild[owner]) == 0:
        del tobuild[owner]


print "<p>%s packages need rebuilding:</p><hr/>" % len(unbuilt)

# Print the results
print '<dl>'
for owner in sorted(tobuild.keys()):
    print '<dt>%s (%s):</dt>' % (owner, len(tobuild[owner]))
    for pkg in sorted(tobuild[owner]):
        print '<dd><a href="http://koji.fedoraproject.org/koji/packageinfo?packageID=%s">%s</a></dd>' % (pkg, pkg)
    print '</dl>'
print '<p>The script that generated this page can be found at '
print '<a href="https://fedorahosted.org/rel-eng/browser/scripts">https://fedorahosted.org/rel-eng/browser/scripts</a>.'
print 'There you can also report bugs and RFEs.</p>'
print '</body>'
print '</html>'
