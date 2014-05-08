#!/usr/bin/python
#
# koji-reimport.py: Reset builds and re-import corrupt noarch packages 
# on secondary kojis. 
#
# Copyright (c) 2014 Red Hat, Inc. 
#
# SPDX-License-Identifier: GPL-2.0
#
# Authors: 
#   David Aquilina <dwa@redhat.com>

import os
import subprocess
import koji
import tempfile
import shutil

# fill these in: 
# pkgs to re-import: 
pkgs = ['']
# tag to tag them with: 
tag = ''

# setup koji sessions: 
serverca = os.path.expanduser('~/.fedora-server-ca.cert')
clientca = os.path.expanduser('~/.fedora-upload-ca.cert')
clientcrt = os.path.expanduser('~/.fedora.cert')
primarykoji = 'https://koji.fedoraproject.org/kojihub'
secondarykoji = 'https://ppc.koji.fedoraproject.org/kojihub' 
primary = koji.ClientSession(primarykoji)
secondary = koji.ClientSession(secondarykoji)
secondary.ssl_login(clientcrt, clientca, serverca) 

# do the thing: 

for pkg in pkgs: 
    print 'Parsing package '+pkg
    # get build info: 
    buildinfo = primary.getBuild(pkg)
    # reset the build on secondary: 
    secondary.untagBuild(tag, pkg)
    secondary.resetBuild(pkg)
    # create an empty build: 
    secondary.createEmptyBuild(buildinfo['package_name'], buildinfo['version'], buildinfo['release'], buildinfo['epoch'])
    # quick and dirty from here... 
    # create temporary dir, throw rpms into it: 
    tempdir = tempfile.mkdtemp() 
    subprocess.call(['koji', 'download-build', pkg], cwd=tempdir) 
    # verify RPMs are good, if so, import them:
    subprocess.check_call(['rpm -K *.rpm'], cwd=tempdir, shell=True)
    subprocess.call(['ppc-koji import *.rpm'], cwd=tempdir, shell=True)
    # Tag: 
    secondary.tagBuild(tag, pkg) 
    # Remove the temp dir
    shutil.rmtree(tempdir)

