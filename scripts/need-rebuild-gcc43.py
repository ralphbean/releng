#!/usr/bin/python

# Copyright (C) 2013 Red Hat, Inc.
# SPDX-License-Identifier:      GPL-2.0+
# template for finding builds that meet some time/buildroot component critera.
# Edit to suit.

import koji
import datetime

## releng folks, update the blacklist below for packages that the maintainer
## wishes to opt-out of autorebuilding.

blacklist = []
#['thunderbird','banshee','epiphany','epiphany-extensions','libipoddevice','malaga-suomi-voikko','bless','sysvinit','mecab-ipadic','mecab-jumandic','kazehakase','qt','knetworkmanager','autogen','bacula','xfdesktop','fontforge',
#'anjuta','gengetopt','pida','openbabel','plplot','paraview']

kojisession = koji.ClientSession('http://koji.fedoraproject.org/kojihub')
tocheck = []
needbuild = []
reallyneedbuild = []
ownermap = {}

print datetime.datetime.isoformat(datetime.datetime.utcnow())

f9builds = kojisession.listTagged('f20', inherit=True, latest=True)
pkgs = kojisession.listPackages('f20', inherited=True)

for pkg in pkgs:
    ownermap[pkg['package_name']] = pkg['owner_name']

for build in f9builds:
    if build['creation_time'] < '2013-11-09 23:43:46.000000':
        tocheck.append(build)

checknum = len(tocheck)

for build in tocheck:
    if build['name'] in blacklist:
        continue
    print "Checking %s (%s of %s)" % (build['nvr'], tocheck.index(build)+1, checknum)
    if not build['task_id']:
        rpms = kojisession.listRPMs(buildID=build['build_id'])
        for rpm in rpms:
            if rpm['arch'] != 'src' and rpm['arch'] != 'noarch':
                needbuild.append(build)
                continue
        continue
    for task in kojisession.getTaskChildren(build['task_id']):
        if build in needbuild:
            continue
        if task['method'] == 'buildArch':
            if task['arch'] == 'noarch':
                print "noarch build, skipping task", task['id']
                continue
            for rootid in kojisession.listBuildroots(taskID=task['id']):
                for pkg in kojisession.listRPMs(componentBuildrootID=rootid['id']):
                    if pkg['name'] == 'gcc':
                        if pkg['version'] == '4.8.2' and pkg['release'] == '1.fc20' :
                            if not build in needbuild:
                                print "adding", build['name']
                                needbuild.append(build)
                                continue
            continue

rebuildnames = []
for build in needbuild:
    if not build in reallyneedbuild:
        reallyneedbuild.append(build)
        rebuildnames.append("%s %s" % (ownermap[build['name']], build['name']))

rebuildnames.sort()
for build in rebuildnames:
    print build
