#!/usr/bin/python

# koji-stalk: Monitors fedmsg for completed builds on koji.fedoraproject.org
# Copyright (C) 2013 Red Hat, Inc. 
#
#    koji-stalk is free software; you can redistribute it and/or
#    modify it under the terms of the GNU Lesser General Public
#    License as published by the Free Software Foundation; 
#    version 2.1 of the License.
#
#    This software is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#    Lesser General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public
#    License along with this software; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA
#
# Authors:
#       David Aquilina <dwa@redhat.com>


import fedmsg
import threading 
from collections import deque
import time
import koji
import subprocess
import re
import logging
import os
import ConfigParser
from optparse import OptionParser

parser = OptionParser() 
parser.add_option("-c", "--config-file", dest="shadowconfig",
                  default="/etc/koji-shadow/koji-shadow.conf",
                  help="koji-shadow configuration file")
parser.add_option("--shadow", dest="shadowcommand", 
                  help="path to koji-shadow", default="/usr/sbin/koji-shadow")
parser.add_option("-l", "--logdir", dest="logdir", 
                  help="directory to write logs to", 
                  default="/mnt/koji/reports/koji-stalk")
parser.add_option("-t", "--test", dest="testonly", action="store_true",
                  help="Only monitor fedmsg without building", default=False)
parser.add_option("--threads", type="int", default="3", 
                  help="number of threads per distro")

(options, args) = parser.parse_args()

### Begin Configuration ###

# distributions to build for:
distronames = ['f17', 'f18', 'f19', 'f20']

# which is rawhide?
rawhide = 'f20'

# koji setup
auth_cert = os.path.expanduser('~/.fedora.cert')
auth_ca = os.path.expanduser('~/.fedora-server-ca.cert')
serverca = os.path.expanduser('~/.fedora-server-ca.cert')
remote = koji.ClientSession('http://koji.fedoraproject.org/kojihub')

# Configuration options below have been converted to use options. 
# If you want to hard-code values for yourself, do it here:

# number of threads (i.e. max simultaneous koji-shadow instances) per distro
threads = options.threads 

# Don't actually build anything or attempt to tag, write logs to /tmp
testonly = options.testonly

# koji-shadow configuration
shadowcommand = options.shadowconfig
shadowconfig = options.shadowconfig
logdir = options.logdir


### End configuration ### 

# Do some stuff for testing mode:
if testonly:
    shadowcommand = '/bin/echo'
    logdir = '/tmp'

# logging setup 
# Setting up two handlers lets us simultaneously log to a file & to stdout
# TODO: Rotate and/or only keep X amount of logs
logger = logging.getLogger('KojiStalk')
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler(os.path.join(logdir, 'KojiStalk.log'))
fh.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
format = logging.Formatter('%(asctime)s - %(levelname)s:  %(message)s')
ch.setFormatter(format)
fh.setFormatter(format)
logger.addHandler(ch)
logger.addHandler(fh)


# Have to warn about testing /after/ we set up the logger...
if testonly:
    logger.warn("Running in test mode!")

# parse the koji-shadow config file, login to our koji:
ks_config = ConfigParser.ConfigParser()
ks_config.read(shadowconfig)
local = koji.ClientSession(ks_config.get("main", "server"))
local.ssl_login(auth_cert, auth_ca, serverca)

# set up the queues
buildqueue = deque()

distqueues = {}
for distro in distronames:
    distqueues[distro] = deque() 

class KojiStalk(threading.Thread):
    """ Use fedmsg to monitor what koji.fp.o is building""" 
    def __init__(self, buildqueue):
        threading.Thread.__init__(self)
        self.buildqueue = buildqueue

    def run(self):
        # fedmsg configuration
        config = fedmsg.config.load_config([], None)
        config['mute'] = True
        config['timeout'] = 0

        # parse the koji-shadow configuration to ignore packages we know
        # we don't care about.
        ignorelist = (ks_config.get('rules', 'excludelist').split() + 
            ks_config.get('rules', 'ignorelist').split())

        logger.debug('Monitoring fedmsg.')
        for name, endpoint, topic, msg in fedmsg.tail_messages(**config):
            if (msg['topic'] == 
                'org.fedoraproject.prod.buildsys.build.state.change' and 
                msg['msg']['new'] == 1 and 
                msg['msg']['name'] not in ignorelist):
                buildqueue.append(msg['msg']['name']+'-'+msg['msg']['version']+'-'+msg['msg']['release'])

class BuildFromDistroQueues(threading.Thread):
    def __init__(self, distro):
        threading.Thread.__init__(self)
        self.distro = distro
        self.distroistqueues = distqueues

    def run(self):
        while True:
            # excessive debugging:
            #logger.debug('Checking queue for %s', self.distro)
            if distqueues[self.distro]:  
                build_nvr(distqueues[self.distro].popleft(), self.distro)
            else:
                time.sleep(60)

def sort_nvr(nvr):
    """ Query koji.fp.o for the target used for a build, then dump the NVR 
        into the appropriate distro-specific queue """
    logger.debug('Analyzing %s', nvr)
    data = remote.getBuild(nvr)
    buildtarget = remote.getTaskRequest(data['task_id'])[1]
    for distro in distronames:
        if re.search(distro, buildtarget):
            distqueues[distro].append(nvr)
            #logger.debug('Placing %s in %s', nvr, distro)
            return
    if re.search('rawhide', buildtarget):
        distqueues[rawhide].append(nvr)
    else:
        logger.info('Ignored %s from %s', nvr, buildtarget)

def build_nvr(nvr, distro):
    """ Use koji-shadow to build a given NVR """
    # Pull newer deps from the -build tag to catch any updates & overrides
    buildtag = distro+'-build'
    if distro == rawhide:
        desttag = rawhide 
    else:
        desttag = distro+'-updates-candidate'
    # Log koji-shadow output
    shadowlog = open(os.path.join(logdir, nvr), 'w')
    # The command line parameters assume that prefer-new and import-noarch are 
    # specified in your koji-shadow config file. You should also be using a 
    # version of koji-shadow which supports prefer-new and --build in combination
    build = subprocess.call([shadowcommand, '-c', shadowconfig, 
                            '--build', nvr, buildtag], stdout=shadowlog, 
                            stderr=shadowlog)
    # koji-shadow doesn't return exit codes, so the only way we know a
    # build failed is if tagging the NVR fails. 
    if not testonly:
        try:
            local.tagBuild(desttag, nvr)
            logger.info('Built & tagged: %s', nvr)
            # If we got this far, we don't care about the log file.
            os.unlink(os.path.join(logdir, nvr))
        except: 
            logger.warn('Failed build: %s', nvr)
    else:
        logger.info('Test Mode: Parsed %s', nvr)
    
    

def main():

    # Start the thread that listens to fedmsg
    ks = KojiStalk(buildqueue) 
    ks.daemon = True
    logger.debug('KojiStalk thread starting')
    ks.start()

    # Start the threads that listen to the distro build queues. 
    for distro in distronames:
        for i in range(threads):
            buildthread = BuildFromDistroQueues(distro)
            buildthread.daemon = True
            buildthread.start()
 
    logger.debug('Monitoring NVRs queue')
    while True:
        # Sort NVRs we get from fedmsg into dist-specific queues, or wait
        # for more NVRs to show up if the queue is empty.
        if buildqueue: 
            nvr = buildqueue.popleft()
            sort_nvr(nvr)
        else:
            # Every 10 minutes, print the queues
            if int(time.strftime('%M')) % 10 == 0:
                for distro in distronames:
                    if distqueues[distro]:
                        logger.debug('%s queue: %s', distro, distqueues[distro])
            time.sleep(60)

main()
