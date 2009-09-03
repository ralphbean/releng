#!/usr/bin/python
#
# prune-tag.py - A utility to prune all but the latest build in a given tag.
#
# Copyright (c) 2009 Red Hat
#
# Authors:
#     Jesse Keating <jkeating@redhat.com>
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
#
# This program requires koji installed, as well as configured.

import os
import optparse
import sys
import koji
import logging

status = 0
builds = {}
untag = []
loglevel = ''
KOJIHUB = 'https://koji.fedoraproject.org/kojihub'
# Should probably set these from a koji config file
SERVERCA = os.path.expanduser('~/.fedora-server-ca.cert')
CLIENTCA = os.path.expanduser('~/.fedora-upload-ca.cert')
CLIENTCERT = os.path.expanduser('~/.fedora.cert')
# Setup a dict of our key names as sigul knows them to the actual key ID
# that koji would use.  We should get this from sigul somehow.

# Define our usage
usage = 'usage: %prog [options] tag'
# Create a parser to parse our arguments
parser = optparse.OptionParser(usage=usage)
parser.add_option('-v', '--verbose', action='count', default=0,
                  help='Be verbose, specify twice for debug')
parser.add_option('-n', '--dry-run', action='store_true', default=False,
                  help='Perform a dry run without untagging')

# Get our options and arguments
(opts, args) = parser.parse_args()

if opts.verbose <= 0:   
    loglevel = logging.WARNING
elif opts.verbose == 1:
    loglevel = logging.INFO 
else: # options.verbose >= 2
    loglevel = logging.DEBUG


logging.basicConfig(format='%(levelname)s: %(message)s',
                    level=loglevel)

# Check to see if we got any arguments
if not args:
    parser.print_help()
    sys.exit(1)

tag = args[0]

# setup the koji session
logging.info('Setting up koji session')
kojisession = koji.ClientSession(KOJIHUB)
if not kojisession.ssl_login(CLIENTCERT, CLIENTCA, SERVERCA):
    logging.error('Unable to log into koji')
    sys.exit(1)

# Get a list of tagged packages
logging.info('Getting builds from %s' % tag)
tagged = kojisession.listTagged(tag)

logging.debug('Got %s builds' % len(builds))

# Sort builds by package
for b in tagged:
    builds.setdefault(b['package_name'], []).append(b)

# Find the packages with multiple builds
for pkg in sorted(builds.keys()):
    if len(builds[pkg]) > 1:
        logging.debug('Leaving newest build %s' % builds[pkg][0]['nvr'])
        for build in builds[pkg][1:]:
            logging.debug('Adding %s to untag list' % build['nvr'])
            untag.append(build['nvr'])

# Now untag all the builds
logging.info('Untagging %s builds' % len(untag))
if not opts.dry_run:
    kojisession.multicall = True
for build in untag:
    if not opts.dry_run:
        kojisession.untagBuildBypass(tag, build, force=True)
    logging.debug('Untagging %s' % build)

if not opts.dry_run:
    results = kojisession.multiCall()

    for build, result in zip(untag, results):
        if isinstance(result, dict):
            logging.error('Error tagging %s' % build)
            if result['traceback']:
                logging.error('    ' + result['traceback'][-1])
            status = 1

logging.info('All done, pruned %s builds.' % len(untag))
sys.exit(status)
