#!/usr/bin/python

# template for finding builds that meet some time/buildroot component critera.
# Edit to suit.

import koji

kojisession = koji.ClientSession('http://koji.fedoraproject.org/kojihub')
potentials = []
tocheck = []
needbuild = []
reallyneedbuild = []

f8builds = kojisession.listTagged('dist-f8', inherit=True, latest=True)

for build in f8builds:
    if build['creation_time'] > '2007-06-12 04:01:15.000000':
        potentials.append(build)

for build in potentials:
    if build['creation_time'] < '2007-07-31 02:10:19.000000':
        tocheck.append(build)

for build in tocheck:
    for task in kojisession.getTaskChildren(build['task_id']):
        if build in needbuild:
            continue
        if task['method'] == 'buildArch':
            for rootid in kojisession.listBuildroots(taskID=task['id']):
                for pkg in kojisession.listRPMs(componentBuildrootID=rootid['id']):
                    if pkg['name'] == 'binutils':
                        if pkg['version'] == '2.17.50.0.16':
                            if not build in needbuild:
                                needbuild.append(build)
                        elif pkg['version'] == '2.17.50.0.17' and pkg['release'] < '7':
                            if not build in needbuild:
                                needbuild.append(build)
                        else:
                            print "%s had binutils, but it was %s" % (build['nvr'], pkg['nvr'])

rebuildnames = []
for build in needbuild:
    for rpm in kojisession.listBuildRPMs(build['nvr']):
        if rpm['arch'] == 'ppc':
            if not build in reallyneedbuild:
                reallyneedbuild.append(build)
                rebuildnames.append(build['name'])

rebuildnames.sort()
for build in rebuildnames:
    print build
