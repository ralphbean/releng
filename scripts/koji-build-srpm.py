#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2011-2013 Red Hat, Inc.
# SPDX-License-Identifier:      GPL-2.0
# Author: Dan Horák <dhorak@redhat.com>
#
# Grab source rpm for a build from primary koji and build it in secondary koji
#

import os
import sys
import koji
import logging
import urlgrabber.grabber as grabber
import urlgrabber.progress as progress
import time
import random
import string

# get architecture, tag/target and build from command line
if len(sys.argv) > 3:
    if sys.argv[1] == '--scratch':
	scratch = True
	i = 1
    else:
	scratch = False
	i = 0
    SECONDARY_ARCH = sys.argv[i+1]
    tag = sys.argv[i+2]
    builds = sys.argv[i+3:]
else:
    print("Build srpm in secondary koji")
    print("Usage: %s [--scratch] <arch> <target> <build> ...<build-N>" % sys.argv[0])
    exit(0)

LOCALKOJIHUB = 'https://%s.koji.fedoraproject.org/kojihub' % (SECONDARY_ARCH)
REMOTEKOJIHUB = 'https://koji.fedoraproject.org/kojihub'
PACKAGEURL = 'http://kojipkgs.fedoraproject.org/'

# Should probably set these from a koji config file
SERVERCA = os.path.expanduser('~/.fedora-server-ca.cert')
CLIENTCA = os.path.expanduser('~/.fedora-upload-ca.cert')
CLIENTCERT = os.path.expanduser('~/.fedora.cert')

loglevel = logging.DEBUG
logging.basicConfig(format='%(levelname)s: %(message)s',
                    level=loglevel)

def _unique_path(prefix):
    """Create a unique path fragment by appending a path component
    to prefix.  The path component will consist of a string of letter and numbers
    that is unlikely to be a duplicate, but is not guaranteed to be unique."""
    # Use time() in the dirname to provide a little more information when
    # browsing the filesystem.
    # For some reason repr(time.time()) includes 4 or 5
    # more digits of precision than str(time.time())
    return '%s/%r.%s' % (prefix, time.time(),
                      ''.join([random.choice(string.ascii_letters) for i in range(8)]))


# setup the koji session
logging.info('Setting up koji session')
localkojisession = koji.ClientSession(LOCALKOJIHUB)
remotekojisession = koji.ClientSession(REMOTEKOJIHUB)
localkojisession.ssl_login(CLIENTCERT, CLIENTCA, SERVERCA)

pg = progress.TextMeter()

for build in builds:
    buildinfo = remotekojisession.getBuild(build)

#    print("build=%s" % (buildinfo))

    if buildinfo == None:
	print("build %s doesn't exist" % (pkg))
	break


    fname = "%s.src.rpm" % buildinfo['nvr']
    url = "%s/packages/%s/%s/%s/src/%s" % (PACKAGEURL, buildinfo['package_name'], buildinfo['version'], buildinfo['release'], fname)

    if not os.path.isfile(fname):
	file = grabber.urlgrab(url, progress_obj = pg, text = "%s" % (fname))

    serverdir = _unique_path('cli-build')
    print("uploading %s ..." % (build))
    localkojisession.uploadWrapper(fname, serverdir, blocksize=65536)
    source = "%s/%s" % (serverdir, fname)

    if scratch:
	opts = {}
	opts['scratch'] = True
    else:
	opts = None

    localkojisession.build(source, tag, opts=opts, priority=2)

    logging.info("submitted build: %s" % buildinfo['nvr'])
