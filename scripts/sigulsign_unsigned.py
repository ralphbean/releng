#!/usr/bin/python
#
# sigulsign_unsigned.py - A utility to use sigul to sign rpms in koji
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
# This program requires koji and sigul installed, as well as configured.

import os
import optparse
import sys
import koji
import getpass
import subprocess
import logging

status = 0
builds = []
rpmdict = {}
unsigned = []
loglevel = ''
passphrase = ''
KOJIHUB = 'https://koji.fedoraproject.org/kojihub'
# Should probably set these from a koji config file
SERVERCA = os.path.expanduser('~/.fedora-server-ca.cert')
CLIENTCA = os.path.expanduser('~/.fedora-upload-ca.cert')
CLIENTCERT = os.path.expanduser('~/.fedora.cert')
# Setup a dict of our key names as sigul knows them to the actual key ID
# that koji would use.  We should get this from sigul somehow.
KEYS = {'fedora-12': {'id': '57bbccba', 'v3': True},
        'fedora-11': {'id': 'd22e77f2', 'v3': True},
        'fedora-10': {'id': '4ebfc273', 'v3': False},
        'fedora-10-testing': {'id': '0b86274e', 'v3': False}}

# Throw out some functions
def writeRPMs():
    """Use the global rpmdict to write out rpms within.
       Returns 0 for success, 1 for failure"""

    status = 0
    # Use multicall for speed
    logging.info('Calling koji to write %s rpms' % len(rpmdict))
    kojisession.multicall = True
    for rpm in rpmdict.keys():
        logging.debug('Writing out %s with %s' % (rpm, key))
        kojisession.writeSignedRPM(rpm, KEYS[key]['id'])

    # Get the results and check for any errors.
    results = kojisession.multiCall()
    for rpm, result in zip(rpmdict.keys(), results):
        if isinstance(result, dict):
            logging.error('Error writing out %s' % rpm)
            if result['traceback']:
                logging.error('    ' + result['traceback'][-1])
            status = 1

    return status


# Define our usage
usage = 'usage: %prog [options] key (build1, build2)'
# Create a parser to parse our arguments
parser = optparse.OptionParser(usage=usage)
parser.add_option('-v', '--verbose', action='count', default=0,
                  help='Be verbose, specify twice for debug')
parser.add_option('--tag',
                  help='Koji tag to sign, use instead of listing builds')
parser.add_option('--inherit', action='store_true', default=False,
                  help='Use tag inheritance to find builds.')
parser.add_option('--just-write', action='store_true', default=False,
                  help='Just write out signed copies of the rpms')
parser.add_option('--just-sign', action='store_true', default=False,
                  help='Just sign and import the rpms')

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

# Check to see if we either got a tag or some builds
if opts.tag and len(args) > 2:
    logging.error('You must provide either a tag or a build.')
    parser.print_help()
    sys.exit(1)

key = args[0]
logging.debug('Using %s for key %s' % (KEYS[key]['id'], key))
if not key in KEYS.keys():
    logging.error('Unknown key %s' % key)
    parser.print_help()
    sys.exit(1)

# Get the passphrase for the user if we're going to sign something
# (This code stolen from sigul client.py)
if not opts.just_write:
    passphrase = getpass.getpass(prompt='Passphrase for %s: ' % key)

# setup the koji session
logging.info('Setting up koji session')
kojisession = koji.ClientSession(KOJIHUB)
kojisession.ssl_login(CLIENTCERT, CLIENTCA, SERVERCA)

# Get a list of builds
# If we have a tag option, get all the latest builds from that tag,
# optionally using inheritance.  Otherwise take everything after the
# key as a build.
if opts.tag is not None:
    logging.info('Getting builds from %s' % opts.tag)
    builds = [build['nvr'] for build in
              kojisession.listTagged(opts.tag, latest=True,
                                     inherit=opts.inherit)]
else:
    logging.info('Getting builds from arguments')
    builds = args[1:]

logging.debug('Got %s builds' % len(builds))

# Build up a list of rpms to operate on
# use multicall here to speed things up
logging.info('Getting build IDs from Koji')
kojisession.multicall = True
# first get build IDs for all the builds
for b in builds:
    # use strict for now to traceback on bad builds
    kojisession.getBuild(b, strict=True)
binfos = kojisession.multiCall()
# now get the rpms from each build
logging.info('Getting rpms from each build')
kojisession.multicall = True
for [b] in binfos:
    kojisession.listRPMs(buildID=b['id'])
results = kojisession.multiCall()
# stuff all the rpms into our rpm list
for [rpms] in results:
    for rpm in rpms:
        rpmdict['%s.%s.rpm' % (rpm['nvr'], rpm['arch'])] = rpm['id']

logging.debug('Found %s rpms' % len(rpmdict))

# Now do something with the rpms.

# If --just-write was passed, try to write them all out
# We try to write them all instead of worrying about which
# are already written or not.  Calls are cheap, restarting
# mash isn't.
if opts.just_write:
    logging.info('Just writing rpms')
    sys.exit(writeRPMs())

# Since we're not just writing things out, we need to figure out what needs
# to be signed.

# Get unsigned packages
logging.info('Checking for unsigned rpms in koji')
kojisession.multicall = True
# Query for the specific key we're looking for, no results means
# that it isn't signed and thus add it to the unsigned list
for rpm in rpmdict.keys():
    kojisession.queryRPMSigs(rpm_id=rpmdict[rpm], sigkey=KEYS[key]['id'])

results = kojisession.multiCall()
for ([result], rpm) in zip(results, rpmdict.keys()):
    if not result:
        logging.debug('%s is not signed with %s' % (rpm, key))
        unsigned.append(rpm)

logging.debug('Found %s unsigned rpms' % len(unsigned))

# Now run the unsigned stuff through sigul
command = ['sigul', '--batch', 'sign-rpm', '--store-in-koji', '--koji-only']
# See if this is a v3 key or not
if KEYS[key]['v3']:
    command.append('--v3-signature')
command.append(key)
logging.info('Signing rpms via sigul')
for rpm in unsigned:
    logging.debug('Running %s' % subprocess.list2cmdline(command + [rpm]))
    child = subprocess.Popen(command + [rpm], stdin=subprocess.PIPE)
    child.stdin.write(passphrase + '\0')
    ret = child.wait()
    if ret != 0:
        logging.error('Error signing %s' % rpm)
        status = 1

# Now that we've signed things, time to write them out, if so desired.
if not opts.just_sign:
    sys.exit(writeRPMs())

logging.info('All done.')
sys.exit(status)
