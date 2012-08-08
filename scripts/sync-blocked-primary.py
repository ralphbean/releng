#!/usr/bin/python
#
# synd-blocked-primary.py - A utility to sync blocked packages in primary koji 
#                           to a secondary arch for a given tag
#
# Copyright (c) 2011 Red Hat
#
# Authors:
#     Dennis Gilmore <ausil@fedoraproject.org>
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

# Set some variables
# Some of these could arguably be passed in as args.
tags = ['f16', 'f17', 'f18', 'f19'] # tag to check in koji

arches = ['arm', 'ppc', 's390', 'sparc']

# Should probably set these from a koji config file
SERVERCA = os.path.expanduser('~/.fedora-server-ca.cert')
CLIENTCA = os.path.expanduser('~/.fedora-upload-ca.cert')
CLIENTCERT = os.path.expanduser('~/.fedora.cert')

kojisession = koji.ClientSession('https://koji.fedoraproject.org/kojihub')

def getBlocked(kojisession, tag):
    blocked = [] # holding for blocked pkgs
    pkgs = kojisession.listPackages(tagID=tag)
    # Check the pkg list for blocked packages
    for pkg in pkgs:
        if pkg['blocked']:
            blocked.append(pkg['package_name'])
            #print "blocked package %s" % pkg['package_name']
    return blocked

for arch in arches:
    print "== Working on Arch: %s" % arch
    # Create a koji session
    seckojisession = koji.ClientSession('https://%s.koji.fedoraproject.org/kojihub' % arch )
    seckojisession.ssl_login(CLIENTCERT, CLIENTCA, SERVERCA)

    for tag in tags:
        print "=== Working on tag: %s" % tag
        secblocked = [] # holding for blocked pkgs
        toblock = []
        unblock = []

        priblocked = getBlocked(kojisession, tag)
        secblocked = getBlocked(seckojisession, tag)

        for pkg in priblocked:
            if pkg not in secblocked:
                toblock.append(pkg)
                print "need to block %s" % pkg
        
        for pkg in secblocked:
            if pkg not in priblocked:
                unblock.append(pkg)
                print "need to unblock %s" % pkg
        
        seckojisession.multicall = True
        for pkg in toblock:
            print "Blocking: %s" % pkg
            seckojisession.packageListBlock(tag, pkg)

        for pkg in unblock:
            print "UnBlocking: %s" % pkg
            seckojisession.packageListUnblock(tag, pkg)


        listings = seckojisession.multiCall()

    seckojisession.logout()
# Print a blurb about where the code came from
print '\nThe script that generated this page can be found at '
print 'https://fedorahosted.org/rel-eng/browser/scripts/find-unblocked-orphans.py'
print 'There you can also report bugs and RFEs.'
