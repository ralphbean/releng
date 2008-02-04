#!/usr/bin/python

# template for finding builds that meet some time/buildroot component critera.
# Edit to suit.

import koji

kojisession = koji.ClientSession('http://koji.fedoraproject.org/kojihub')
tocheck = []
needbuild = []
reallyneedbuild = []

f9builds = kojisession.listTagged('dist-f9', inherit=True, latest=True)

for build in f9builds:
    if build['creation_time'] < '2008-01-30 15:22:10.000000':
        tocheck.append(build)

checknum = len(tocheck)

for build in tocheck:
    print "Checking %s (%s of %s)" % (build['nvr'], tocheck.index(build)+1, checknum)
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
                        if pkg['version'] < '4.3.0':
                            if not build in needbuild:
                                print "adding", build['name']
                                needbuild.append(build)
                                continue
            continue

rebuildnames = []
for build in needbuild:
    if not build in reallyneedbuild:
        reallyneedbuild.append(build)
        rebuildnames.append(build['name'])

rebuildnames.sort()
for build in rebuildnames:
    print build
