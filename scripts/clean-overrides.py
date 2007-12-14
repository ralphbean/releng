#!/usr/bin/python
#
# clean-overrides.py - A utility to examine a buildroot override tag and
#       compare contents to an updates tag.
#
# Copyright (c) 2007 Red Hat
#
# Authors:
#     Jesse Keating <jkeating@redhat.com>


import koji
import rpm
import sys

def usage():
    print """
    clean-overrides.py overridetag updatetag
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

def printBuild(build):
    pkgdict = koji.parse_NVR(build)
    return '%s-%s-%s' % (pkgdict['name'], pkgdict['version'], pkgdict['release'])

if len(sys.argv) > 1 and sys.argv[1] in ['-h', '--help', '-help', '--usage']:
    usage()
    sys.exit(0)
elif len(sys.argv) < 3:
    usage()
    sys.exit(1)
else:
    overtag, updatetag = sys.argv[1:]

kojisession = koji.ClientSession('http://koji.fedoraproject.org/kojihub')

f7overrides = kojisession.listTagged(overtag)
f7stables = kojisession.listTagged(updatetag, latest=True)

stabledict = {}
equal = []
older = []

for build in f7stables:
    stabledict[build['package_id']] = buildToNvr(build)

for build in f7overrides:
    if build['package_id'] in stabledict.keys():
        rc = compare(buildToNvr(build), stabledict[build['package_id']])
        if rc == 0:
            equal.append(buildToNvr(build))
        if rc < 0:
            older.append(buildToNvr(build))

if equal:
    print "Builds that exist both in %s and %s:" % (overtag, updatetag)
    for build in equal:
        print build
    print ""

if older:
    print "Builds that are older in %s than in %s." % (overtag, updatetag)
    for build in older:
        print build
    print ""

if equal or older:
    print "Suggest: koji untag-pkg --force %s %s %s" % (overtag, ' '.join([printBuild(e) for e in equal]), ' '.join([printBuild(o) for o in older]))
