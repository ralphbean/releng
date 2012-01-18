#!/usr/bin/python
#
# isolate-tag.py - A utility to tag all inherited builds
#                      into a specific koji tag
#
# Copyright (c) 2010 Red Hat
#
# Authors:
#     Nick Petrov <npetrov@redhat.com>
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

tag = 'f16'

# Create a koji session
kojisession = koji.ClientSession('https://koji.fedoraproject.org/kojihub')

# Log into koji
clientcert = os.path.expanduser('~/.fedora.cert')
clientca = os.path.expanduser('~/.fedora-upload-ca.cert')
serverca = os.path.expanduser('~/.fedora-server-ca.cert')
kojisession.ssl_login(clientcert, clientca, serverca)

# Get all builds tagged into the tag w/o inherited builds
builds = kojisession.listTagged(tag, latest=True)

buildlist = []
for build in builds:
    buildlist.append(build['nvr'])

# Get all builds tagged to the tag including inherited builds
allbuilds = kojisession.listTagged(tag, latest=True, inherit=True)

# Isolate all the inherited builds
tagbuilds = []

for build in allbuilds:
    if build['nvr'] not in buildlist:
        tagbuilds.append(build['nvr'])

kojisession.multicall = True

# tag builds
for build in tagbuilds:
    print "tag %s itno %s" % (build, tag)
    kojisession.tagBuildBypass(tag, build)

result = kojisession.multiCall()

