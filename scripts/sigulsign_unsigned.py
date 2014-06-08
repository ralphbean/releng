#!/usr/bin/python
#
# sigulsign_unsigned.py - A utility to use sigul to sign rpms in koji
#
# Copyright (C) 2009-2013 Red Hat, Inc.
# SPDX-License-Identifier:      GPL-2.0
#
# Authors:
#     Jesse Keating <jkeating@redhat.com>
#
# This program requires koji and sigul installed, as well as configured.

import os
import optparse
import sys
import koji
import getpass
import subprocess
import logging

errors = {}

status = 0
builds = []
rpmdict = {}
unsigned = []
loglevel = ''
passphrase = ''
# Should probably set these from a koji config file
SERVERCA = os.path.expanduser('~/.fedora-server-ca.cert')
CLIENTCA = os.path.expanduser('~/.fedora-upload-ca.cert')
CLIENTCERT = os.path.expanduser('~/.fedora.cert')
# Setup a dict of our key names as sigul knows them to the actual key ID
# that koji would use.  We should get this from sigul somehow.
KEYS = {'fedora-12-sparc': {'id': 'b3eb779b', 'v3': True},
        'fedora-13-sparc': {'id': '5bf71b5e', 'v3': True},
        'fedora-14-secondary': {'id': '19be0bf9', 'v3': True},
        'fedora-15-secondary': {'id': '3ad31d0b', 'v3': True},
        'fedora-16-secondary': {'id': '10d90a9e', 'v3': True},
        'fedora-17-secondary': {'id': 'f8df67e6', 'v3': True},
        'fedora-18-secondary': {'id': 'a4d647e9', 'v3': True},
        'fedora-19-secondary': {'id': 'ba094068', 'v3': True},
        'fedora-20-secondary': {'id': 'efe550f5', 'v3': True},
        'fedora-21-secondary': {'id': 'a0a7badb', 'v3': True},
        'fedora-12': {'id': '57bbccba', 'v3': True},
        'fedora-13': {'id': 'e8e40fde', 'v3': True},
        'fedora-14': {'id': '97a1071f', 'v3': True},
        'fedora-15': {'id': '069c8460', 'v3': True},
        'fedora-16': {'id': 'a82ba4b7', 'v3': True},
        'fedora-17': {'id': '1aca3465', 'v3': True},
        'fedora-18': {'id': 'de7f38bd', 'v3': True},
        'fedora-19': {'id': 'fb4b18e6', 'v3': True},
        'fedora-20': {'id': '246110c1', 'v3': True},
        'fedora-21': {'id': '95a43f54', 'v3': True},
        'fedora-11': {'id': 'd22e77f2', 'v3': True},
        'fedora-10': {'id': '4ebfc273', 'v3': False},
        'fedora-10-testing': {'id': '0b86274e', 'v3': False},
        'epel-7': {'id': '352c64e5', 'v3': True},
        'epel-6': {'id': '0608b895', 'v3': True},
        'epel-5': {'id': '217521f6', 'v3': False}}


class KojiHelper(object):
    def __init__(self, arch=None):
        if arch:
            self.kojihub = \
                'http://{arch}.koji.fedoraproject.org/kojihub'.format(
                    arch=arch)
        else:
            self.kojihub = 'https://koji.fedoraproject.org/kojihub'
        self.serverca = os.path.expanduser('~/.fedora-server-ca.cert')
        self.clientca = os.path.expanduser('~/.fedora-upload-ca.cert')
        self.clientcert = os.path.expanduser('~/.fedora.cert')
        self.kojisession = koji.ClientSession(self.kojihub)
        self.kojisession.ssl_login(self.clientcert, self.clientca,
                                   self.serverca)

    def listTagged(self, tag, inherit=False):
        """ Return list of NVRs for a tag
        """
        builds = [build['nvr'] for build in
                  self.kojisession.listTagged(tag, latest=True,
                                              inherit=inherit)
                  ]
        return builds

    def get_build_ids(self, nvrs):
        errors = []

        build_ids = []
        self.kojisession.multicall = True

        for build in nvrs:
            # use strict for now to traceback on bad buildNVRs
            kojisession.getBuild(build, strict=True)

        for build, result in zip(nvrs, kojisession.multiCall()):
            if isinstance(result, list):
                build_ids.append(result[0]["id"])
            else:
                errors.append(build)
        return build_ids, errors


def exit(status):
    """End the program using status, report any errors"""

    if errors:
        for type in errors.keys():
            logging.error('Errors during %s:' % type)
            for fault in errors[type]:
                logging.error('     ' + fault)

    sys.exit(status)


# Throw out some functions
def writeRPMs(status, batch=None):
    """Use the global rpmdict to write out rpms within.
       Returns status, increased by one in case of failure"""

    # Check to see if we want to write all, or just the unsigned.
    if opts.write_all:
        rpms = rpmdict.keys()
    else:
        if batch is None:
            rpms = [rpm for rpm in rpmdict.keys() if rpm in unsigned]
        else:
            rpms = batch
    logging.info('Calling koji to write %s rpms' % len(rpms))
    status = status
    written = 0
    rpmcount = len(rpms)
    while rpms:
        # Use multicall for speed, but break it into chunks of 100
        # so that there is some sense of progress
        kojisession.multicall = True
        workset = rpms[0:100]
        rpms = rpms[100:]

        for rpm in workset:
            written += 1
            logging.debug('Writing out %s with %s, %s of %s',
                          rpm, key, written, rpmcount)
            kojisession.writeSignedRPM(rpm, KEYS[key]['id'])

        # Get the results and check for any errors.
        results = kojisession.multiCall()
        for rpm, result in zip(workset, results):
            if isinstance(result, dict):
                logging.error('Error writing out %s' % rpm)
                errors.setdefault('Writing', []).append(rpm)
                if result['traceback']:
                    logging.error('    ' + result['traceback'][-1])
                status += 1
    return status


def validate_sigul_password(key, password):
    """ Validate sigul password by trying to get the public key, which is an
    authenticated operation
    """
    command = ['sigul', '--batch', 'get-public-key', key]
    child = subprocess.Popen(command, stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
    child.stdin.write(password + '\0')
    ret = child.wait()
    if ret == 0:
        return True
    else:
        return False


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
parser.add_option('--just-list', action='store_true', default=False,
                  help='Just list the unsigned rpms')
parser.add_option('--write-all', action='store_true', default=False,
                  help='Write every rpm, not just unsigned')
parser.add_option('--password',
                  help='Password for the key')
parser.add_option('--batch-mode', action="store_true", default=False,
                  help='Read null-byte terminated password from stdin')
parser.add_option('--arch',
                  help='Architecture when siging secondary arches')
parser.add_option('--sigul-batch-size',
                  help='Amount of RPMs to sign in a sigul batch',
                  default=50, type="int")
# Get our options and arguments
(opts, args) = parser.parse_args()

if opts.verbose <= 0:
    loglevel = logging.WARNING
elif opts.verbose == 1:
    loglevel = logging.INFO
else:  # options.verbose >= 2
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
if not (opts.just_list or opts.just_write):
    if opts.password:
        passphrase = opts.password
    elif opts.batch_mode:
        passphrase = ""
        while True:
            pwchar = sys.stdin.read(1)
            if pwchar == '\0':
                break
            elif pwchar == '':
                raise EOFError('Incomplete password')
            else:
                passphrase += pwchar
    else:
        passphrase = getpass.getpass(prompt='Passphrase for %s: ' % key)

    if not validate_sigul_password(key, passphrase):
        logging.error('Error validating passphrase for key %s' % key)
        sys.exit(1)

# setup the koji session
logging.info('Setting up koji session')
kojihelper = KojiHelper(arch=opts.arch)
kojisession = kojihelper.kojisession

# Get a list of builds
# If we have a tag option, get all the latest builds from that tag,
# optionally using inheritance.  Otherwise take everything after the
# key as a build.
if opts.tag is not None:
    logging.info('Getting builds from %s' % opts.tag)
    builds = kojihelper.listTagged(opts.tag, inherit=opts.inherit)
else:
    logging.info('Getting builds from arguments')
    builds = args[1:]

logging.info('Got %s builds' % len(builds))

# sort the builds
builds = sorted(builds)
buildNVRs = []
cmd_build_ids = []
for b in builds:
    if b.isdigit():
        cmd_build_ids.append(int(b))
    else:
        buildNVRs.append(b)

if buildNVRs != []:
    logging.info('Getting build IDs from Koji')
    build_ids, buildID_errors = kojihelper.get_build_ids(buildNVRs)
    for nvr in buildID_errors:
        logging.error('Invalid n-v-r: %s' % nvr)
        status += 1
        errors.setdefault('buildNVRs', []).append(nvr)
else:
    build_ids = []

build_ids.extend(cmd_build_ids)

# now get the rpms from each build
logging.info('Getting rpms from each build')
kojisession.multicall = True
for bID in build_ids:
    kojisession.listRPMs(buildID=bID)
results = kojisession.multiCall()
# stuff all the rpms into our rpm list
for [rpms] in results:
    for rpm in rpms:
        rpmdict['%s.%s.rpm' % (rpm['nvr'], rpm['arch'])] = rpm['id']

logging.info('Found %s rpms' % len(rpmdict))

# Now do something with the rpms.

# If --just-write was passed, try to write them all out
# We try to write them all instead of worrying about which
# are already written or not.  Calls are cheap, restarting
# mash isn't.
if opts.just_write:
    logging.info('Just writing rpms')
    exit(writeRPMs(status))

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

if opts.just_list:
    logging.info('Just listing rpms')
    print('\n'.join(unsigned))
    exit(status)

logging.debug('Found %s unsigned rpms' % len(unsigned))

if opts.arch:
    # Now run the unsigned stuff through sigul
    command = ['sigul', '--batch', 'sign-rpms', '-k', opts.arch,
               '--store-in-koji', '--koji-only']
else:
    # Now run the unsigned stuff through sigul
    command = ['sigul', '--batch', 'sign-rpms', '--store-in-koji',
               '--koji-only']
# See if this is a v3 key or not
if KEYS[key]['v3']:
    command.append('--v3-signature')
command.append(key)


# run sigul
def run_sigul(rpms, batchnr):
    global status
    logging.debug('Running %s' % subprocess.list2cmdline(command + rpms))
    logging.info('Signing batch %s/%s with %s rpms' % (
        batchnr, (total + batchsize - 1) / batchsize, len(rpms))
    )
    child = subprocess.Popen(command + rpms, stdin=subprocess.PIPE)
    child.stdin.write(passphrase + '\0')
    ret = child.wait()
    if ret != 0:
        logging.error('Error signing %s' % (rpms))
        for rpm in rpms:
            errors.setdefault('Signing', []).append(rpm)
    status += 1

logging.info('Signing rpms via sigul')
total = len(unsigned)
batchsize = opts.sigul_batch_size
batchnr = 0
rpms = []
for rpm in unsigned:
    rpms += [rpm]
    if len(rpms) == batchsize:
        batchnr += 1
        run_sigul(rpms, batchnr)
        rpms = []

if len(rpms) > 0:
    batchnr += 1
    run_sigul(rpms, batchnr)

# Now that we've signed things, time to write them out, if so desired.
if not opts.just_sign:
    exit(writeRPMs(status))

logging.info('All done.')
sys.exit(status)
