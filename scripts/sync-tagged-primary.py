#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# synd-tagged-primary.py - A utility to sync tagged packages in primary koji 
#                           to a secondary arch 
#
# Copyright (c) 2012 Red Hat
#
# Authors:
#     Dennis Gilmore <ausil@fedoraproject.org>
#     Dan Horák <dan@danny.cz>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.

import koji
import os
import sys
import tempfile
import shutil
import rpm
import argparse

# get architecture and tags from command line
parser = argparse.ArgumentParser()
parser.add_argument("--dry-run", help="no changes will be made", action="store_true")
parser.add_argument("arch", help="secondary arch to sync")
parser.add_argument("tag", nargs="+", help="tag to sync")
args = parser.parse_args()

# Should probably set these from a koji config file
SERVERCA = os.path.expanduser('~/.fedora-server-ca.cert')
CLIENTCA = os.path.expanduser('~/.fedora-upload-ca.cert')
CLIENTCERT = os.path.expanduser('~/.fedora.cert')

def getTagged(kojisession, tag):
    tagged = [] # holding for blocked pkgs
    pkgs = kojisession.listTagged(tag, latest=True)
    # Check the pkg list for blocked packages
    #for pkg in pkgs:
    #    tagged.append({"name": pkg['name'], "nvr": pkg['nvr']})
            
    #    print "tagged build %s" % pkg['nvr']
    return pkgs

def rpmvercmp ((e1, v1, r1), (e2, v2, r2)):
    """find out which build is newer"""
    rc = rpm.labelCompare((e1, v1, r1), (e2, v2, r2))
    if rc == 1:
        #first evr wins
        return 1
    elif rc == 0:
        #same evr
        return 0
    else:
        #second evr wins
        return -1


print "=== Working on arch: %s ====" % args.arch
# Create a koji session
kojisession = koji.ClientSession('https://koji.fedoraproject.org/kojihub')
seckojisession = koji.ClientSession('https://%s.koji.fedoraproject.org/kojihub' % args.arch)
seckojisession.ssl_login(CLIENTCERT, CLIENTCA, SERVERCA)

for tag in args.tag:
    print "=== Working on tag: %s ====" % tag
    secblocked = [] # holding for blocked pkgs
    totag = []
    tountag = []
    pripkgnvrs = []
    secpkgnvrs = []

    pripkgs = getTagged(kojisession, tag)
    secpkgs = getTagged(seckojisession, tag)

    for pkg in pripkgs:
        pripkgnvrs.append(pkg['nvr'])
    for pkg in secpkgs:
        secpkgnvrs.append(pkg['nvr'])

    for pkg in pripkgs:
        if pkg['nvr'] not in secpkgnvrs:
            secpkg = seckojisession.getBuild(pkg['nvr'])
            # see if we have the build on secondary koji and make sure its complete
            if not secpkg is None and secpkg['state'] == 1 :
                totag.append(pkg['nvr'])
                print "need to tag %s" % pkg['nvr']

    for pkg in secpkgs:
        if pkg['nvr'] not in pripkgnvrs:
            # make sure we have had a build of the package on primary tagged into the tag
            pripkg = kojisession.tagHistory(tag=tag, package=pkg['name'])
            if pripkg == []:
                # if the package only exists on secondary let it be
                print "Secondary arch only package %s" % pkg['nvr']
            # secondary arch evr is higher than primary untag ours
	    elif pripkg[0]['active'] == None:
                # get the latest build from primary in the tag
                pripkg = kojisession.listTagged(tag, latest=True, package=pkg['name'])
                if pripkg == [] or rpmvercmp((str(pkg['epoch']), pkg['version'], pkg['release']),  (str(pripkg[0]['epoch']), pripkg[0]['version'], pripkg[0]['release'])) == 1:
                    tountag.append(pkg['nvr'])
                    print "need to untag %s" % pkg['nvr']

    if args.dry_run:
        continue

    seckojisession.multicall = True
    for pkg in totag:
        print "Tagging: Arch: %s Tag: %s Package: %s" % (args.arch, tag, pkg)
        seckojisession.tagBuildBypass(tag, pkg)

    for pkg in tountag:
        print "Untagging: Arch: %s Tag: %s Package: %s" % (args.arch, tag, pkg)
        seckojisession.untagBuildBypass(tag, pkg)

    listings = seckojisession.multiCall()

seckojisession.logout()
