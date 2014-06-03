#!/usr/bin/python

# Copyright (C) 2013 Red Hat, Inc.
# SPDX-License-Identifier:      GPL-2.0

import sys
import os
import koji
import logging
import urlgrabber.grabber as grabber
import urlgrabber.progress as progress
import urllib2
import time
import random
import string
import rpm 
import shutil
import argparse
import tempfile

# get parameters from command line
parser = argparse.ArgumentParser()
parser.add_argument("--force", help="reimport a failed build", action="store_true")
parser.add_argument("--verbose", help="be verbose during processing", action="store_true")
parser.add_argument("arch", help="secondary arch koji where to import the builds")
parser.add_argument("tag", help="import to this tag")
parser.add_argument("build", nargs="*", help="build to import")
args = parser.parse_args()

LOCALKOJIHUB = 'https://%s.koji.fedoraproject.org/kojihub' % (args.arch)
REMOTEKOJIHUB = 'https://koji.fedoraproject.org/kojihub'
PACKAGEURL = 'http://kojipkgs.fedoraproject.org/'

# Should probably set these from a koji config file
SERVERCA = os.path.expanduser('~/.fedora-server-ca.cert')
CLIENTCA = os.path.expanduser('~/.fedora-upload-ca.cert')
CLIENTCERT = os.path.expanduser('~/.fedora.cert')

workpath = tempfile.mkdtemp(prefix="koji-import.")

loglevel = logging.DEBUG
logging.basicConfig(format='%(levelname)s: %(message)s',
                    level=loglevel)

pg = progress.TextMeter()

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

def isNoarch(rpms):
    if not rpms:
        return False
    noarch = False
    for rpminfo in rpms:
        if rpminfo['arch'] == 'noarch':
            #note that we've seen a noarch rpm
            noarch = True
        elif rpminfo['arch'] != 'src':
            return False
    return noarch

def tagSuccessful(nvr, tag):
    """tag completed builds into final tags"""
    localkojisession.tagBuildBypass(tag, nvr)
    logging.info("tagged %s to %s" % (nvr, tag))

def _downloadURL(url, destf):
    """Download a url and save it to a file"""
    file = grabber.urlopen(url, progress_obj = pg, text = "%s" % (destf))

    out = os.open(destf, os.O_WRONLY|os.O_CREAT|os.O_TRUNC, 0666)
    try:
        while 1:
            buf = file.read(4096)
            if not buf:
                break
            os.write(out, buf)
    finally:
        os.close(out)
        file.close()

def _importURL(url, fn):
    """Import an rpm directly from a url"""
    serverdir = _unique_path('build-recent')
    #TODO - would be possible, using uploadFile directly, to upload without writing locally.
    #for now, though, just use uploadWrapper
    koji.ensuredir(workpath)
    dst = "%s/%s" % (workpath, fn)
    logging.info("Downloading %s to %s..." % (url, dst))
    _downloadURL(url, dst)
    #fsrc = urllib2.urlopen(url)
    #fdst = file(dst, 'w')
    #shutil.copyfileobj(fsrc, fdst)
    #fsrc.close()
    #fdst.close()
    logging.info("Uploading %s..." % dst)
    localkojisession.uploadWrapper(dst, serverdir, blocksize=65536)
    localkojisession.importRPM(serverdir, fn)

def importBuild(rpms, buildinfo, tag=None):
    '''import a build from remote hub'''
    for rpminfo in rpms:
        if rpminfo['arch'] == 'src':
            srpm = rpminfo
    pathinfo = koji.PathInfo(PACKAGEURL)

    build_url = pathinfo.build(buildinfo)
    url = "%s/%s" % (pathinfo.build(buildinfo), pathinfo.rpm(srpm))
    fname = "%s.src.rpm" % buildinfo['nvr']
    try:
        _importURL(url, fname)
    except:
	logging.error("Importing %s failed" % fname)
	return False
    else:
        for rpminfo in rpms:
	    if rpminfo['arch'] == 'src':
    		#already imported above
        	continue
    	    relpath = pathinfo.rpm(rpminfo)
    	    url = "%s/%s" % (build_url, relpath)
    	    logging.debug("url: %s" % url)
    	    fname = os.path.basename(relpath)
    	    logging.debug("fname: %s" % fname)
	    try:
    		_importURL(url, fname)
	    except:
		logging.error("Importing %s failed" % fname)
		return False

	tagSuccessful(buildinfo['nvr'], tag)
	return True

# setup the koji session
logging.info('Setting up koji session')
localkojisession = koji.ClientSession(LOCALKOJIHUB)
remotekojisession = koji.ClientSession(REMOTEKOJIHUB)
localkojisession.ssl_login(CLIENTCERT, CLIENTCA, SERVERCA)

for build in args.build:
    buildinfo = remotekojisession.getBuild(build)

    logging.info("got build %s" % buildinfo['nvr'])

    rpms = remotekojisession.listRPMs(buildinfo['id'])
    if isNoarch(rpms):
	buildinfo = remotekojisession.getBuild(buildinfo['id'])
        if args.force:
            localkojisession.resetBuild(buildinfo['nvr'])
            localkojisession.createEmptyBuild(buildinfo['package_name'], buildinfo['version'], buildinfo['release'], buildinfo['epoch'])
	importBuild(rpms, buildinfo, tag=args.tag)
    else:
	logging.error("not a pure noarch build")

shutil.rmtree(workpath)
