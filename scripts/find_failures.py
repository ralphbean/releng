#!/usr/bin/python
#
# find-failures.py - A utility to discover failed builds in a given tag
#                    Output is currently rough html
#
# Copyright (c) 2009 Red Hat
#
# Authors:
#     Jesse Keating <jkeating@redhat.com>
#

import koji
import operator
import datetime

# Set some variables
# Some of these could arguably be passed in as args.
buildtag = 'f18-rebuild' # tag to check
desttag = 'f18' # Tag where fixed builds go
epoch = '2012-07-17 14:18:03.000000' # Date to check for failures from
failures = {} # dict of owners to lists of packages that failed.
failed = [] # raw list of failed packages


def get_failed_builds(kojisession, epoch, buildtag, desttag):
    """This function returns list of all failed builds since epoch within
    buildtag that were not rebuilt succesfully in desttag

    Keyword arguments:
    kojisession -- connected koji.ClientSession instance
    epoch -- string representing date to start looking for failed builds
             from. Format: "%F %T.%N"
    buildtag -- tag where to look for failed builds (usually fXX-rebuild)
    desttag -- tag where to look for succesfully built packages
    """
    # Get a list of failed build tasks since our epoch
    failtasks = sorted(kojisession.listBuilds(createdAfter=epoch, state=3),
                       key=operator.itemgetter('task_id'))

    # Get a list of successful builds tagged
    goodbuilds = kojisession.listTagged(buildtag, latest=True)

    # Get a list of successful builds after the epoch in our dest tag
    destbuilds = kojisession.listTagged(desttag, latest=True, inherit=True)
    for build in destbuilds:
        if build['creation_time'] > epoch:
            goodbuilds.append(build)

    pkgs = kojisession.listPackages(desttag, inherited=True)

    # get the list of packages that are blocked
    pkgs = sorted([pkg for pkg in pkgs if pkg['blocked']],
                  key=operator.itemgetter('package_id'))

    # Check if newer build exists for package
    failbuilds = []
    for build in failtasks:
        if ((not build['package_id'] in [goodbuild['package_id'] for goodbuild in goodbuilds]) and (not build['package_id'] in [pkg['package_id'] for pkg in pkgs])):
            failbuilds.append(build)

    # Generate taskinfo for each failed build
    kojisession.multicall = True
    for build in failbuilds:
        kojisession.getTaskInfo(build['task_id'], request=True)

    taskinfos = kojisession.multiCall()
    for build, [taskinfo] in zip(failbuilds, taskinfos):
        build['taskinfo'] = taskinfo
    # Get owners of the packages with failures
    kojisession.multicall = True
    for build in failbuilds:
        kojisession.listPackages(tagID=buildtag,
                                 pkgID=build['package_id'],
                                 inherited=True)
    pkginfo = kojisession.multiCall()

    for build, [pkg] in zip(failbuilds, pkginfo):
        build['package_owner'] = pkg[0]['owner_name']
    return failbuilds


if __name__ == '__main__':
    # Create a koji session
    kojisession = koji.ClientSession('https://koji.fedoraproject.org/kojihub')

    failbuilds = get_failed_builds(kojisession, epoch, buildtag, desttag)


    # Generate the dict with the failures and urls
    for build in failbuilds:
        if not build['taskinfo']['request'][1] == buildtag:
            continue
        taskurl = 'http://koji.fedoraproject.org/koji/taskinfo?taskID=%s' % build['task_id']
        owner = build['package_owner']
        pkg = build['package_name']
        if not pkg in failed:
            failed.append(pkg)
        failures.setdefault(owner, {})[pkg] = taskurl

    now = datetime.datetime.now()
    now_str = "%s UTC" % str(now.utcnow())
    print '<html><head>'
    print '<title>Packages that failed to build as of %s</title>' % now_str
    print '<style type="text/css"> dt { margin-top: 1em } </style>'
    print '</head><body>'
    print "<p>Last run: %s</p>" % now_str

    print '%s failed builds:<p>' % len(failed)

    # Print the results
    print '<dl>'
    print '<style type="text/css"> dt { margin-top: 1em } </style>'
    for owner in sorted(failures.keys()):
        print '<dt>%s (%s):</dt>' % (owner, len(failures[owner]))
        for pkg in sorted(failures[owner].keys()):
            print '<dd><a href="%s">%s</a></dd>' % (failures[owner][pkg], pkg)
    print '</dl>'
    print '</body>'
    print '</html>'
