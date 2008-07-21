#!/usr/bin/python
#
# check-upgrade-paths.py - A utility to examine a set of tags to verify upgrade
#       paths for all the packages.
#
# Copyright (c) 2008 Red Hat
#
# Authors:
#     Jesse Keating <jkeating@redhat.com>


import koji
import rpm
import sys

def usage():
    print """
    check-upgrade-paths.py tag1 tag2 [tag3 tag4]
    tags must be in ascending order, f8-gold dist-f8-updates dist-f8-updates-testing dist-f9-updates ...
    """

def compare(pkgA, pkgB):
    pkgdictA = koji.parse_NVR(pkgA)
    pkgdictB = koji.parse_NVR(pkgB)

    rc = rpm.labelCompare((pkgdictA['epoch'], pkgdictA['version'], pkgdictA['release']),
                         (pkgdictB['epoch'], pkgdictB['version'], pkgdictB['release']))

    return rc

def buildToNvr(build):
    if build['epoch']:
        return '%s:%s' % (build['epoch'], build['nvr'])
    else:
        return build['nvr']

if len(sys.argv) > 1 and sys.argv[1] in ['-h', '--help', '-help', '--usage']:
    usage()
    sys.exit(0)
elif len(sys.argv) < 3:
    usage()
    sys.exit(1)
else:
    tags = sys.argv[1:]

kojisession = koji.ClientSession('http://koji.fedoraproject.org/kojihub')
tagdict = {}
pkgdict = {}
badpaths = {}

# Use multicall to get the latest tagged builds from each tag
kojisession.multicall = True
for tag in tags:
    kojisession.listTagged(tag, latest=True, inherit=True)

results = kojisession.multiCall()

# Stuff the results into a dict of tag to builds
for tag, result in zip(tags, results):
    tagdict[tag] = result[0]

# Populate the pkgdict with a set of package names to tags to nvrs
for tag in tags:
    for pkg in tagdict[tag]:
        if not pkgdict.has_key(pkg['name']):
            pkgdict[pkg['name']] = {}
        pkgdict[pkg['name']][tag] = buildToNvr(pkg)

# Loop through the packages, compare e:n-v-rs from the first tag upwards
# then proceed to the next given tag and again compare upwards
for pkg in pkgdict:
    for tag in tags[:-1]: # Skip the last tag since there is nothing to compare it to
        for nexttag in tags[tags.index(tag)+1:]: # Compare from current tag up
            if pkgdict[pkg].has_key(tag):
                if pkgdict[pkg].has_key(nexttag): # only compare if the next tag knows about this package
                    rc = compare(pkgdict[pkg][tag], pkgdict[pkg][nexttag])
                    if rc <= 0:
                        continue
                    if rc > 0:
                        # We've got something broken here.
                        if not badpaths.has_key(pkg):
                            badpaths[pkg] = []
                        badpaths[pkg].append('%s > %s (%s %s)' % (tag, nexttag, pkgdict[pkg][tag], pkgdict[pkg][nexttag]))

# TODO We should print ownership here
print """Broken upgrade path report for tags %s""" % tags
print "\n"
pkgs = badpaths.keys()
pkgs.sort()
for pkg in pkgs:
    print "%s:" % pkg
    for path in badpaths[pkg]:
        print "    %s" % path
    print "\n"
