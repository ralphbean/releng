#!/usr/bin/python -tt
# A library for accessing and working with EC2.
# Author: Jay Greguske  <jgregusk@redhat.com>
# Copyright (C) 2013 Red Hat Inc.
# SPDX-License-Identifier:	GPL-2.0+

import boto.ec2
import logging
import os
from socket import gethostname
import subprocess
import sys
import time

# we assume all RH accounts have access to these
pvgrubs = {
  'public': {
    'part': {
      'sa-east-1':      {'i386': 'aki-bc3ce3a1', 'x86_64': 'aki-cc3ce3d1'},
      'us-east-1':      {'i386': 'aki-407d9529', 'x86_64': 'aki-427d952b'},
      'us-west-1':      {'i386': 'aki-99a0f1dc', 'x86_64': 'aki-9ba0f1de'},
      'us-west-2':      {'i386': 'aki-c2e26ff2', 'x86_64': 'aki-98e26fa8'},
      'eu-west-1':      {'i386': 'aki-4deec439', 'x86_64': 'aki-4feec43b'},
      'ap-southeast-1': {'i386': 'aki-13d5aa41', 'x86_64': 'aki-11d5aa43'},
      'ap-southeast-2': {'i386': 'aki-9b8413a1', 'x86_64': 'aki-998413a3'},
      'ap-northeast-1': {'i386': 'aki-d209a2d3', 'x86_64': 'aki-d409a2d5'}}}
}

def get_pvgrub(public, disk, region, arch):
    """
    Return the AKI ID that matches parameters given:
        public - boolean; whether the image is public (True) or private
        disk - boolean; whether a disk image (True) or partition image
        region - ec2 region
        arch - i386 or x86_64
    Throws an Fedora_EC2Error if no image matches.
    """
    if public:
        pub = 'public'
    else:
        pub = 'private'
    if disk:
        dis = 'disk'
    else:
        dis = 'part'
    try:
        return pvgrubs[pub][dis][region][arch]
    except KeyError:
        raise Fedora_EC2Error('No matching PVGrub found (%s)' %
            ', '.join((pub, dis, region, arch)))

#
# Classes
#

class Fedora_EC2Error(Exception):
    """Custom exception for this library"""
    pass

class EC2Cred(object):
    """
    Encapsulate EC2 credentials in an object for simple access. They are drawn
    from the usual environment variables EC2 tools expect.
    """

    def __init__(self):
        creds = {}
        for env_var in ('EC2_ACCOUNT', 'EC2_ACCESS_KEY', 'EC2_SECRET_KEY', 'EC2_CERT', 'EC2_PRIVATE_KEY'):
            creds[env_var] = os.environ.get(env_var)
        if None in creds.values():
            raise RuntimeError, 'Missing environment variable(s): %s' % \
                ', '.join([k for k in creds.keys() if creds[k] == None])
        self.account = creds['EC2_ACCOUNT']
        self.cert = creds['EC2_CERT']
        self.private = creds['EC2_PRIVATE_KEY']
        self.access = creds['EC2_ACCESS_KEY']
        self.secret = creds['EC2_SECRET_KEY']

class EC2Obj(object):
    """
    An object that encapsulates useful information that is specific to Fedora's
    EC2 infrastructure and environments. Provides many methods to interact
    with EC2 in a standarized way.
    """

    # SSH key <-> region mappings for AWS accounts
    keypath = os.path.expanduser('.')
    keys = {
        '125523088429': { # fedaws
            'sa-east-1':      'releng-sa-east-1',
            'us-east-1':      'releng-us-east',
            'us-west-1':      'releng-us-west',
            'us-west-2':      'releng-us-west-2',
            'eu-west-1':      'releng-eu-west',
            'ap-southeast-1': 'releng-ap-southeast',
            'ap-southeast-2': 'releng-ap-southeast-2',
            'ap-northeast-1': 'releng-ap-northeast'}
    }

    _instances = 1
    _devs = {}
    _devs.update([('/dev/sd' + chr(i), None) for i in range(104, 111)])

    def __init__(self, region='US', cred=None, quiet=False, logfile=None, 
                 debug=False, test=False):
        """
        Constructor; useful options to the object are interpreted here.
        EC2Objs are region specific and we want to support a script
        instanciating multiple EC2Objs, so some identity management and cross-
        object data is maintained as class variables. EC2Objs are NOT
        serialized!

        cred: a valid EC2Cred object
        quiet: Do not print to stdout
        logfile: path to write the log for use of this object
        debug: enable debug output
        test: enable test mode. test mode only displays the command we would
              run, and all methods return None
        """
        # logging
        format = logging.Formatter("[%(asctime)s %(name)s %(levelname)s]: %(message)s")
        if logfile == None:
            logfile = '%s.%s.log' % (__name__, EC2Obj._instances)
        logname = os.path.basename(logfile)
        if logname.endswith('.log'):
            logname = logname[:-4]
        logdir = os.path.dirname(logfile)
        if logdir != '' and not os.path.exists(logdir):
            os.makedirs(logdir)
        self.logger = logging.getLogger(logname)
        self.testmode = test
        if self.testmode:
            debug = True
        if debug: 
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger.setLevel(logging.INFO)
        file_handler = logging.FileHandler(logfile)
        file_handler.setFormatter(format)
        self.logger.addHandler(file_handler)
        if not quiet:
            stdout_handler = logging.StreamHandler(sys.stdout)
            stdout_handler.setFormatter(format)
            self.logger.addHandler(stdout_handler)

        # check environment
        for tool in ('euca-run-instances',   'euca-describe-instances',
                     'euca-create-volume',   'euca-attach-volume',
                     'euca-detach-volume',   'euca-describe-volumes',
                     'euca-create-snapshot', 'euca-describe-snapshots',
                     'euca-register',        'euca-delete-snapshot',
                     'euca-delete-volume',   'euca-terminate-instances',
                     'euca-modify-image-attribute'):
            try:
                self.run_cmd('which %s' % tool)
            except Fedora_EC2Error:
                self.logger.warning('%s is missing!' % tool)

        # object initialization
        if cred == None:
            self.cred = EC2Cred()
        else:
            self.cred = cred
        self.region = self.alias_region(region)
        self.rurl = 'http://ec2.%s.amazonaws.com' % self.region
        self.logger.debug('Region: %s' % self.region)
        self.logger.debug('Credentials:\n  Account: %s\n  Cert: %s\n  PK: %s' %
            (self.cred.account, self.cred.cert, self.cred.private))
        self.def_zone = '%sb' % self.region
        self.def_group = 'Basic'
        self.id = EC2Obj._instances
        self._att_devs = {}
        self.logger.debug('Initialized EC2Obj #%s' % EC2Obj._instances)
        EC2Obj._instances += 1

    def alias_region(self, reg):
        """
        EC2 tools are not consistent about region labels, so we try to be 
        friendly about that here.
        """
        region = reg
        if reg in ('US', 'us-east'):
            region = 'us-east-1'
        elif reg == 'us-west':
            region = 'us-west-1'
        elif reg in ('EU', 'eu-west'):
            region = 'eu-west-1'
        elif reg == 'ap-southeast':
            region = 'ap-southeast-1'
        elif reg == 'ap-northeast':
            region = 'ap-northeast-1'
        elif reg in ('sa-east-1', 'us-east-1', 'us-west-1', 'us-west-2', 'eu-west-1', 'ap-southeast-1',
                     'ap-southeast-2', 'ap-northeast-1'):
            # these are what we want, do nothing
            pass
        else:
            self.logger.warn('Unrecognized region: %s' % region)
        return region

    def ami_info(self, ami_id):
        """
        Return a dictionary that describes an AMI:
        id - the AMI id
        source - the bucket/name of the AMI
        owner - account number of the owner
        status - AMI status, normally 'available'
        visibility - 'public' or 'private'
        product - products codes associated with it (devpay)
        arch - i386 or x86_64
        type - type of image ('machine', 'kernel', 'ramdisk')
        aki - the AKI ID
        ari - the ARI ID (empty string for pvgrub)
        snapid - snapshot id of of the EBS volume it was registered from
        """
        info = {}
        if not ami_id.startswith('ami-'):
            raise Fedora_EC2Error('Only an AMI ID can be passed to this method')
        output = self.run_cmd('euca-describe-images -U %s %s' %
            (self.rurl, ami_id))[0]
        if self.testmode: return None
        lines = output.split('\n')
        if len(lines) > 1:
            bits = lines[1].split('\t')
            if bits[0] == 'BLOCKDEVICEMAPPING':
                info['snapid'] = bits[3]
        attrs = ('id', 'source', 'owner', 'status', 'visibility', 'product',
                 'arch', 'type', 'aki', 'ari')
        bits = lines[0].split('\t')
        for i in range(len(attrs)):
            try:
                info[attrs[i]] = bits[i+1]
            except IndexError:
                info[attrs[i]] = '' # ari is missing sometimes
        self.logger.debug('Retrieved image info: %s' % info)
        return info

    def deregister_ami(self, ami_id):
        """De-Register an AMI. Returns the ID of the AMI"""
        output = self.run_cmd('euca-deregister -U %s %s' %
            (self.rurl, ami_id))[0]
        if self.testmode: return None
        id = output.split('\t')[1]
        self.logger.info('De-Registered an AMI: %s' % id)
        return id

    def start_ami(self, ami, aki=None, ari=None, wait=False, zone=None,
                  group=None, keypair=None, disk=True):
        """
        Start the designated AMI. This function does not guarantee success. See
        inst_info to verify an instance started successfully. 
        Optionally takes a few keyword arguments:
            - wait: True if we should wait until the instance is running
            - aki: the AKI id to start with. Setting it to 'pvgrub' will cause
                   us to boot with the appropriate pvgrub AKI ID. Setting it to
                   None will boot it with the default it was bundled with.
            - ari: the ARI id to start with
            - zone: the availability zone to start in
            - group: the security group to start the instance in
            - keypair: SSH key pair to log in with
        Returns a dictionary describing the instance, see inst_info().
        """
        ami_info = self.ami_info(ami)
        if zone == None:
            zone = self.def_zone
        if group == None:
            group = self.def_group
        if keypair == None:
            keypair = self.keys[self.cred.account][self.region]
        cmd = 'euca-run-instances -U %s -k %s -n 1 -z %s -g "%s" %s ' % (self.rurl, keypair, zone, group, ami)
        if ari != None:
            cmd += '--ramdisk %s ' % ari
        if aki == 'pvgrub':
            # technically it doesn't matter if we use the public or private AKI
            cmd += '--kernel %s ' % get_pvgrub(True, disk, self.region,
                ami_info['arch'])
        elif aki != None:
            cmd += '--kernel %s ' % aki
        print ami_info['arch']
        if ami_info['arch'] == 'i386':
            cmd += '-t m1.small '
        elif ami_info['arch'] == 'x86_64':
            cmd += '-t m1.large '
        else:
            self._log_error('Unsupported arch: %s' % ami_info['arch'])
        if self.testmode:
            self.run_cmd(cmd)
            return None
        lines = self.run_cmd(cmd)[0].splitlines()
        inst_id = lines[1].split('\t')[1]
        if wait:
            info = self.wait_inst_status(inst_id, 'running')
        else:
            info = self.inst_info(inst_id)
        self._att_devs[info['id']] = EC2Obj._devs.copy()
        self.logger.info('Started an instance of %s: %s' % (ami, info['id']))
        return info

    def inst_info(self, id):
        """
        Return information about an instance. Returns a dictionary:
            id - The instance ID
            ami - The AMI ID
            group - the Security Group it booted with
            account - the account number the instance belongs to
            reservation - the reservation number for the resources
            status - instance status (pending, running, terminated, etc)
            keypair - the SSH keypair
            index
            type - the instance type string such as m1.large
            zone - availability zone
            aki - the AKI ID it is booting with
            ari - the ARI ID it is booting with (empty string for pvgrubs)
            time - the time the instance was started
            url - the url/hostname of the instance
            address - the IP address
        """
        info = {}
        output = self.run_cmd('euca-describe-instances -U %s %s' %
            (self.rurl, id))[0]
        if self.testmode: return None
        lines = output.splitlines()
        bits = lines[0].split('\t')
        info['reservation'], info['account'], info['group']  = bits[1:]
        bits = lines[1].split('\t')
        attrs = ('id', 'ami', 'url', 'address', 'status', 'keypair', 'index',
                 'vpc', 'type', 'time', 'zone', 'aki', 'ari')
        for i in range(len(attrs)):
            try:
                info[attrs[i]] = bits[i+1]
            except IndexError:
                info[attrs[i]] = '' # ari is missing sometimes
        self.logger.debug('Retrieved instance info: %s' % info)
        return info

    def get_url(self, id):
        """Return the URL address of a running instance"""
        info = self.inst_info(id)
        if self.testmode: return None
        if info['url'] == '':
            self.logger.warning('Sought URL for %s but it is not defined' % id)
        return info['url']

    def wait_inst_status(self, id, status, tries=0, interval=20):
        """
        Wait until an instance has the desired status. Optional arguments 
        tries and interval set how many tries and how long to wait between 
        polls respectively. Will throw an error if the status is ever 
        terminated, unless that is the desired status. Setting tries to 0 means
        to try forever. Returns a dictionary describing the instance, see
        inst_info().
        """
        forever = False
        if tries == 0:
            forever = True
        timer = 1
        while timer <= tries or forever:
            current = self.inst_info(id)
            if self.testmode: return None
            if current['status'] == status:
                return current
            if current['status'] == 'terminated':
                self._log_error('%s is in the terminated state!' % id)
            self.logger.info('Try #%s: %s is not %s, sleeping %s seconds' %
                (timer, id, status, interval))
            time.sleep(interval)
            timer += 1
        self._log_error('Timeout exceeded for %s to be %s' % (id, status))

    def _take_dev(self, inst_id, vol_id):
        """
        Internal method to get the next available device name to use when
        attaching an EBS volume to an instance. Throws an error if we have
        run out, 10 is the max.
        """
        if self._att_devs.get(inst_id) == None:
            self._att_devs[inst_id] = EC2Obj._devs.copy()
        try:
            dev = [d for d in self._att_devs[inst_id].keys() 
                if self._att_devs[inst_id][d] == None].pop()
        except IndexError:
            self._log_error('No free device names left for %s' % inst_id)
        self._att_devs[inst_id][dev] = vol_id
        self.logger.debug('taking %s to attach %s to %s' % 
            (dev, vol_id, inst_id))
        return dev

    def _release_dev(self, inst_id, vol_id):
        """
        Internal method to release a device name back into the pool when
        detaching from an instance. Throws an error if the device is already
        unattached, since this should never happen.
        """
        if vol_id not in self._att_devs[inst_id].values():
            self._log_error('Device is not attached! (%s from %s)' %
                (vol_id, inst_id))
        dev = [d for d in self._att_devs[inst_id].keys()
            if self._att_devs[inst_id][d] == vol_id].pop()
        self._att_devs[inst_id][dev] = None
        self.logger.debug('releasing %s from %s for %s' % 
            (dev, inst_id, vol_id))
        return dev

    def create_vol(self, size, zone=None, wait=False, snap=None):
        """
        Create an EBS volume of the given size in region/zone. If size == 0,
        do not explicitly set a size; this may be useful with "snap", which
        creates a volume from a snapshot ID.
        
        This function does not guarantee success, you should check with
        vol_available() to ensure it was created successfully. If wait is set
        to True, we will wait for the volume to be available before returning;
        returns a dictionary describing the volume, see vol_info().
        """
        if zone == None:
            zone = self.def_zone
        cmd = 'euca-create-volume -z %s -U %s' % (zone, self.rurl)
        if size > 0:
            cmd += ' --size %s' % size
        if snap != None:
            cmd += ' --snapshot %s' % snap
        output = self.run_cmd(cmd)[0]
        if self.testmode: return None
        id = output.split('\t')[1]
        if wait:
            info = self.wait_vol_status(id, 'available')
        else:
            info = self.vol_info(id)
        self.logger.info('Created an EBS volume: %s' % info['id'])
        return info

    def attach_vol(self, inst_id, vol_id, wait=False, dev=None):
        """
        Attach an EBS volume to an AMI id in region. This is not an immediate 
        action, you should check the status of the volume (see vol_info) if
        you wish to do something more with it after attaching. Setting wait to
        True cause the method to wait until the volume is attached before
        returning. Can can be used to manually set the device name, otherwise
        one will be selected automatically. Returns a dictionary describing the
        volume, see vol_info().
        """
        if dev == None:
            dev = self._take_dev(inst_id, vol_id)
        else:
            if not dev.startswith('/dev/sd'):
                self._log_error('Not a valid device name: %s' % dev)
        self.run_cmd('euca-attach-volume -U %s %s -i %s -d %s' %
            (self.rurl, vol_id, inst_id,dev))
        if self.testmode: return None
        if wait:
            info = self.wait_vol_status(vol_id, 'attached')
        else:
            info = self.vol_info(vol_id)
        self.logger.info('attached %s to %s' % (vol_id, inst_id))
        return info

    def detach_vol(self, inst_id, vol_id, wait=False):
        """
        Detach an EBS volume from an instance. Note that this action is not
        immediate, you should check the status of the volume if you wish to do
        something more with it after detaching (see vol_info). Setting wait to
        True will make the method wait until the volume is detached before
        returning. Returns a dictionary describing the volume, see vol_info().
        """
        self.run_cmd('euca-detach-volume -U %s %s -i %s' %
            (self.rurl, vol_id, inst_id))
        if self.testmode: return None
        if wait:
            info = self.wait_vol_status(vol_id, 'available')
        else:
            info = self.vol_info(vol_id)
        self._release_dev(inst_id, vol_id)
        self.logger.info('Detached %s from %s' % (vol_id, inst_id))
        return info

    def vol_info(self, vol_id):
        """
        Get status on a volume. Returns a dictionary with the following fields:
        id - the volume ID
        size - the size in gigabytes of the volume
        snapshot
        zone - availability zone
        status - available, creating, ...
        time - the time the volume was created

        If the volume is attached, additional fields will be available:
        instance - the instance ID it is attached to
        device - the device name it is exposed as
        attach_status - status of the attachment
        attach_time - when the volume was attached
        """
        output = self.run_cmd("euca-describe-volumes -U %s %s" % 
            (self.rurl, vol_id))[0]
        if self.testmode: return None
        info = {}
        lines = output.splitlines()
        attrs = ('id', 'size', 'snapshot', 'zone', 'status', 'time')
        bits = lines[0].split('\t')
        for i in range(len(attrs)):
            info[attrs[i]] = bits[i+1]
        if len(lines) == 2:
            bits = lines[1].split('\t')
            attrs = ('instance', 'device', 'attach_time')
            # euca2ools do not have this field :(
            info['attach_status'] = 'attached'
            for i in range(len(attrs)):
                info[attrs[i]] = bits[i+2]
        self.logger.debug('Retrieved volume info: %s' % info)
        return info

    def wait_vol_status(self, vol_id, status, tries=0, interval=20):
        """
        Wait until a volume has the desired status. Optional arguments tries 
        and interval set how many tries and how long to wait between polls 
        respectively. Will throw a RuntimeError if the status is ever 
        'deleting', unless that is the desired status. Setting tries to 0 means
        to try forever. Returns a dictionary describing the volume, see
        vol_info().
        """
        forever = False
        if tries == 0:
            forever = True
        timer = 1
        while timer <= tries or forever:
            current = self.vol_info(vol_id)
            if self.testmode: return None
            if status in (current['status'], current.get('attach_status')):
                return current
            if 'deleting' in (current['status'], current.get('attach_status')):
                raise RuntimeError, '%s is being deleted!' % vol_id
            self.logger.info('Try #%s: %s not %s, sleeping %s seconds' %
                (timer, vol_id, status, interval))
            time.sleep(interval)
            timer += 1
        self._log_error('Timeout exceeded waiting for %s to be %s' %
            (vol_id, status))

    def take_snap(self, vol_id, wait=False):
        """
        Snapshot a detached volume, returns the snapshot ID. If wait is set to
        True, return once the snapshot is created. Returns a dictionary 
        that describes the snapshot.
        """
        vol_info = self.vol_info(vol_id)
        out = self.run_cmd('euca-create-snapshot  -U %s %s' %
            (self.rurl, vol_id))[0]
        if self.testmode: return None
        snap_id = out.split('\t')[1]
        if wait:
            info = self.wait_snap_status(snap_id, 'completed')
        else:
            info = self.snap_info(snap_id)
        self.logger.info('snapshot %s taken' % snap_id)
        return info

    def snap_info(self, snap_id):
        """
        Return a dictionary that describes a snapshot:
        id - the snapshot ID
        vol_id - the volume ID the snapshot was taken from
        status - pending, completed, etc
        time - when the snapshot was created
        """
        output = self.run_cmd('euca-describe-snapshots -U %s %s' %
            (self.rurl, snap_id))[0]
        if self.testmode: return None
        bits = output.split('\t')
        info = {}
        attrs = ('id', 'vol_id', 'status', 'time')
        for i in range(len(attrs)):
            info[attrs[i]] = bits[i+1]
        self.logger.debug('Retrieved snapshot info: %s' % info)
        return info

    def wait_snap_status(self, snap_id, status, tries=0, interval=20):
        """
        Wait until a snapshot is completes. Optional arguments tries and
        interval set how many tries and how long to wait between polls
        respectively. Setting tries to 0 means to try forever. Returns nothing.
        """
        forever = False
        if tries == 0:
            forever = True
        timer = 1
        while timer <= tries or forever:
            current = self.snap_info(snap_id)
            if self.testmode: return None
            if current['status'] == status:
                return current
            self.logger.info('Try #%s: %s is not %s, sleeping %s seconds' %
                (timer, snap_id, status, interval))
            time.sleep(interval)
            timer += 1
        self._log_error('Timeout exceeded for %s to be %s' % (snap_id, status))

    def register_snap(self, snap_id, arch, name, aki=None, desc=None, ari=None,
                      disk=False):
        """
        Register an EBS volume snapshot as an AMI. Returns the AMI ID. An arch,
        snapshot ID, and name for the AMI must be provided. Optionally
        a description, AKI ID, and ARI ID may be specified too.
        disk is whether or not we are registering a disk image.
        """
        if aki == None:
            aki = get_pvgrub(True, disk, self.region, arch)
        cmd = 'euca-register -a %s -U %s -b /dev/sdf=ephemeral0 -b /dev/sdg=ephemeral1 -n "%s"' % \
            (arch, self.rurl, name)
        if disk:
            cmd += ' --virtualization-type hvm'
            cmd += ' -b /dev/sda=%s --root-device-name /dev/sda' % snap_id
        else:
            cmd += ' --kernel %s' % aki
            cmd += ' -b /dev/sda1=%s --root-device-name /dev/sda1' % snap_id
        if ari != None:
            cmd += ' --ramdisk %s' % ari
        if desc != None:
            cmd += ' -d "%s"' % desc
        if self.testmode:
            self.run_cmd(cmd)
            return None
        output = self.run_cmd(cmd)[0].strip()
        ami_id = output.split('\t')[1]
        if not ami_id.startswith('ami-'):
            self._log_error('Could not register an AMI')
        self.logger.info('Registered an AMI: %s' % ami_id)
        return ami_id

    def register_snap2(self, snap_id, arch, name, aki=None, desc=None,
                       disk=False):
        """Just like register_snap, except use boto"""
        # need to define conn
        conn = boto.ec2.connect_to_region(self.region,
            aws_access_key_id=self.cred.access,
            aws_secret_access_key=self.cred.secret)
        if aki == None and not disk:
            aki = get_pvgrub(True, disk, self.region, arch)
        if disk:
            dev = '/dev/sda'
        else:
            dev = '/dev/sda1'
        ebs = boto.ec2.blockdevicemapping.EBSBlockDeviceType()
        ebs.snapshot_id = snap_id
        block_map = boto.ec2.blockdevicemapping.BlockDeviceMapping()
        block_map[dev] = ebs
        if disk:
            result = conn.register_image(name=name,
                description='Official Fedora AMI - %s' % name,
                architecture=arch, 
                root_device_name=dev, block_device_map=block_map)
        else:
            result = conn.register_image(name=name,
                description='Official Fedora AMI - %s' % name,
                architecture=arch, kernel_id=aki,
                root_device_name=dev, block_device_map=block_map)
        self.logger.info('Registered an AMI: %s' % result)
        return result

    def delete_snap(self, snap_id):
        """
        USE WITH CAUTION!

        Delete an EBS volume snapshot. Returns the ID of the snapshot that was
        deleted.
        """
        out = self.run_cmd('euca-delete-snapshot -U %s %s' % 
            (self.rurl, snap_id))[0]
        if self.testmode: return None
        self.logger.info('Deleted a snapshot: %s' % snap_id)
        return out.split('\t')[1].strip()

    def delete_vol(self, vol_id):
        """
        USE WITH CAUTION!

        Delete an EBS volume. If snapshotted already it is safe to do this.
        Returns the id of the volume that was deleted.
        """
        output = self.run_cmd('euca-delete-volume -U %s %s' % 
            (self.rurl, vol_id))[0]
        if self.testmode: return None
        self.logger.info('Deleted a volume: %s' % vol_id)
        return output.split('\t')[1].strip()

    def kill_inst(self, inst_id, wait=False):
        """
        USE WITH CAUTION!
        
        Kill a running instance. Returns a dictionary describing the instance,
        see inst_info for more information. Setting wait=True means we will not
        return until the instance is terminated.
        """
        self.run_cmd('euca-terminate-instances -U %s %s' %
            (self.rurl, inst_id))
        if self.testmode: return None
        if wait:
            inst_info = self.wait_inst_status(inst_id, 'terminated')
        else:
            inst_info = self.inst_info(inst_id)
        self.logger.info('Killed an instance: %s' % inst_id)
        return inst_info

    def grant_access(self, ami, acct):
        """
        Grant an account launch permissions to an AMI.
        """
        self.run_cmd(
            'euca-modify-image-attribute -U %s %s -l -a %s' %
            (self.rurl, ami, acct))
        if self.testmode: return None
        self.logger.info('granted launch permissions of %s to %s' %
            (ami, acct))

    def revoke_access(self, ami, acct):
        """
        Revoke launch permissions of an account for an AMI.
        """
        self.run_cmd(
            'euca-modify-image-attribute -U %s %s -l -r %s' %
            (self.rurl, ami, acct))
        if self.testmode: return None
        self.logger.info('revoked launch permissions of %s for %s' %
            (ami, acct))

    def make_public(self, ami):
        """
        Make an AMI publicly launchable. Should be used for Hourly images only!
        """
        self.run_cmd(
            'euca-modify-image-attribute -U %s %s -l -a all' % (self.rurl, ami))
        if self.testmode: return None
        self.logger.info('%s is now public!' % ami)

    def get_my_insts(self):
        """
        Return a list of dicts that describe all running instances this account
        owns. See inst_info for a description of the dict.
        """
        mine = []
        output = self.run_cmd('euca-describe-instances %s -U %s' %
            (self.rurl))[0].splitlines()
        if self.testmode: return None
        info = {}
        for inst in output:
            bits = inst.split('\t')
            if bits[0] == 'RESERVATION':
                info['reservation'], info['account'], info['group']  = bits[1:]
            else:
                attrs = ('id', 'ami', 'url', 'address', 'status', 'keypair',
                         'index', 'vpc', 'type', 'time', 'zone', 'aki', 'ari')
                for i in range(len(attrs)):
                    try:
                        info[attrs[i]] = bits[i+1]
                    except IndexError:
                        info[attrs[i]] = '' # ari is missing sometimes
                mine.append(info)
                info = {}
            self.logger.debug('Retrieved instance info: %s' % info)
        return mine

    def get_my_amis(self):
        """
        Return a list of dicts that describe all AMIs this account owns. See
        ami_info for a description of the dict; there is one difference though.
        The snapid field may contain a list of snapshots in the blockmapping
        for an image. It does not take just the first one.
        """
        output = self.run_cmd('euca-describe-images -U %s -o self' %
            (self.rurl))[0].split('\n')
        if self.testmode: return None
        attrs = ('id', 'source', 'owner', 'status', 'visibility', 'product',
                 'arch', 'type', 'aki', 'ari')
        mine = []
        info = {'snapid': []}
        for image in output:
            bits = image.split('\t')
            if bits[0] == 'BLOCKDEVICEMAPPING':
                info['snapid'].append(bits[3])
            elif bits[0] == 'IMAGE':
                if info.get('id') != None and info.get('id').startswith('ami-'):
                    # we don't want AKIs or ARIs
                    mine.append(info.copy())
                    info = {'snapid': []}
                for i in range(len(attrs)):
                    try:
                        info[attrs[i]] = bits[i+1]
                    except IndexError:
                        info[attrs[i]] = ''
        # do this once more to get the last line
        if info.get('id') != None and info.get('id').startswith('ami-'):
            mine.append(info.copy())
        self.logger.debug(str(mine))
        return mine

    def get_my_snaps(self):
        """
        Return a list of dicts that describe all snapshots owned by this
        account. See snap_info for a description of the dict.
        """
        output = self.run_cmd('euca-describe-snapshots -U %s -o self' %
            (self.rurl))[0].split('\n')
        if self.testmode: return None
        mine = []
        for snap in output:
            bits = snap.split('\t')
            info = {}
            attrs = ('id', 'vol_id', 'status', 'time')
            for i in range(len(attrs)):
                info[attrs[i]] = bits[i+1]
            mine.append(info.copy())
        self.logger.debug('Retrieved my snapshots: %s' % mine)
        return mine

    # utility methods

    def run_cmd(self, cmd):
        """
        Run a command and collect the output and return value.
        """
        self.logger.debug('Command: %s' % cmd)
        if self.testmode:
            # Always return good status; we're just testing the commands
            return 0, 0
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, shell=True)
        ret = proc.wait()
        output = proc.stdout.read().strip()
        self.logger.debug('Return code: %s' % ret)
        self.logger.debug('Output: %s' % output)
        if ret != 0:
            self.logger.error('Command had a bad exit code: %s' % ret)
            self.logger.error('Command run: %s' % cmd)
            self.logger.error('Output:\n%s' % output)
            raise Fedora_EC2Error('Command failed, see logs for output')
        return output, ret

    def _log_error(self, msg):
        """report and throw an error"""
        self.logger.error(msg)
        raise Fedora_EC2Error(msg)

    # SSH-specific methods

    def get_ssh_opts(self):
        """return ssh options we want to use throughout this script"""
        kp = os.path.join(self.keypath, 
            self.keys[self.cred.account][self.region]) + '.pem'
        ssh_opts = '-i %s ' % kp + \
                   '-o "StrictHostKeyChecking no" ' + \
                   '-o "PreferredAuthentications publickey"'
        return ssh_opts

    def run_ssh(self, instance, cmd):
        """ssh to an instance and run a command"""
        ssh_opts = self.get_ssh_opts()
        ssh_host = 'root@%s' % instance['url']
        return self.run_cmd('ssh %s %s "%s"' % (ssh_opts, ssh_host, cmd))

    def wait_ssh(self, instance, tries=0, interval=20):
        """
        Continually attempt to ssh into an instance and return when we can.
        This useful for when an instance is booting and we have to wait until
        ssh is available.
        """
        forever = False
        if tries == 0:
            forever = True
        timer = 1
        while timer <= tries or forever:
            try:
                return self.run_ssh(instance, 'true')
            except Fedora_EC2Error:
                self.logger.warning('SSH failed, sleeping for %s seconds' %
                    interval)
                time.sleep(interval)
                timer += 1
        raise Fedora_EC2Error('Could not SSH in after %s tries' % tries)

