#!/usr/bin/python
#
# check-upgrade-paths.py - A utility to examine a set of tags to verify upgrade
#       paths for all the packages.
#
# Copyright (c) 2008 Red Hat
#
# Authors:
#     Jesse Keating <jkeating@redhat.com>
#
# This script is loosely based on previous Extras script found at http://cvs.fedoraproject.org/viewcvs/upgradecheck/upgradecheck.py
# We don't actually do checking of subpackages, nor upgrade testing with Obsoletes/Provides.  In an ideal world these kinds of
# tests would be done as part of automated testing post-build or post-update submission.  We're getting close to these things
# so I decided to leave it out of this script for now.
#
# We also don't generate a owner sorted list of packages, instead we create a /builder/ sorted list, since
# the builder is the more interesting person involved.
#
# This script will mail the owners and the builder of packages that are broken directly
# as well as send a mail to a mailing list with an overall report.


import koji
import rpm
import sys
import smtplib
import datetime

fromaddr = 'buildsys@fedoraproject.org'
toaddr = 'fedora-devel-list@redhat.com'
domain = '@fedoraproject.org'
smtpserver = 'localhost'

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

def genPackageMail(builder, package):
    """Send a mail to the package watchers and the builder regarding the break.
       Mail is set out once per broken package."""

    # This relies on the package-owner alias sets
    addresses = [builder, '%s-owner' % package]
    msg = """From: %s
To: %s
Subject: Broken upgrade path(s) detected for: %s

""" % (fromaddr, ','.join([addy+domain for addy in addresses]), package)

    for path in badpaths[pkg]:
        msg += "    %s\n" % path

    msg += "\n\nPlease fix the(se) issue(s) as soon as possible.\n"

    msg += "\n---------------\n"
    msg += "This report generated by Fedora Release Engineering, using http://git.fedorahosted.org/git/?p=releng;a=blob;f=scripts/check-upgrade-paths.py;hb=HEAD"

    try:
        server = smtplib.SMTP(smtpserver)
        server.set_debuglevel(1)
        server.sendmail(fromaddr, [addy+domain for addy in addresses], msg)
    except:
        print 'sending mail failed'

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
badpathsbybuilder = {}

# Use multicall to get the latest tagged builds from each tag
kojisession.multicall = True
for tag in tags:
    kojisession.listTagged(tag, latest=True)

results = kojisession.multiCall()

# Stuff the results into a dict of tag to builds
for tag, result in zip(tags, results):
    tagdict[tag] = result[0]

# Populate the pkgdict with a set of package names to tags to nvrs
for tag in tags:
    for pkg in tagdict[tag]:
        if not pkgdict.has_key(pkg['name']):
            pkgdict[pkg['name']] = {}
        pkgdict[pkg['name']][tag] = {'nvr': buildToNvr(pkg), 'builder': pkg['owner_name']}

# Loop through the packages, compare e:n-v-rs from the first tag upwards
# then proceed to the next given tag and again compare upwards
for pkg in pkgdict:
    for tag in tags[:-1]: # Skip the last tag since there is nothing to compare it to
        for nexttag in tags[tags.index(tag)+1:]: # Compare from current tag up
            if pkgdict[pkg].has_key(tag):
                if pkgdict[pkg].has_key(nexttag): # only compare if the next tag knows about this package
                    rc = compare(pkgdict[pkg][tag]['nvr'], pkgdict[pkg][nexttag]['nvr'])
                    if rc <= 0:
                        continue
                    if rc > 0:
                        # We've got something broken here.
                        if not badpaths.has_key(pkg):
                            badpaths[pkg] = []
                        if not badpathsbybuilder.has_key(pkgdict[pkg][tag]['builder']):
                            badpathsbybuilder[pkgdict[pkg][tag]['builder']] = {}
                        if not badpathsbybuilder[pkgdict[pkg][tag]['builder']].has_key(pkg):
                            badpathsbybuilder[pkgdict[pkg][tag]['builder']][pkg] = []
                        badpaths[pkg].append('%s > %s (%s %s)' % (tag, nexttag, pkgdict[pkg][tag]['nvr'], pkgdict[pkg][nexttag]['nvr']))
                        badpathsbybuilder[pkgdict[pkg][tag]['builder']][pkg].append('%s > %s (%s %s)' % (tag, nexttag, pkgdict[pkg][tag]['nvr'], pkgdict[pkg][nexttag]['nvr']))

msg = """From: %s
To: %s
Subject: Package EVR problems in Fedora %s

""" % (fromaddr, toaddr, datetime.date.today())
msg += "Broken upgrade path report for tags %s:\n" % ' -> '.join(tags)

pkgs = badpaths.keys()
pkgs.sort()
for pkg in pkgs:
    msg += "%s:\n" % pkg
    for path in badpaths[pkg]:
        msg += "    %s\n" % path
    msg += "\n"

msg += "-----------------------\n"
msg += "Broken paths by builder:\n"
builders = badpathsbybuilder.keys()
builders.sort()
for builder in builders:
    msg += "%s:\n" % builder
    pkgs = badpathsbybuilder[builder].keys()
    pkgs.sort()
    for pkg in pkgs:
        genPackageMail(builder, pkg)
        msg += "    %s:\n" % pkg
        for path in badpathsbybuilder[builder][pkg]:
            msg += "        %s\n" % path
    msg += "\n"

msg += "---------------\n"
msg += "This report generated by Fedora Release Engineering, using http://git.fedorahosted.org/git/?p=releng;a=blob;f=scripts/check-upgrade-paths.py;hb=HEAD"

try:
    server = smtplib.SMTP(smtpserver)
    server.set_debuglevel(1)
    server.sendmail(fromaddr, toaddr, msg)
except:
    print 'sending mail failed'
