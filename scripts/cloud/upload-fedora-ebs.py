#!/usr/bin/python -tt
# Upload images to EBS volumes in EC2 in all regions
# Author: Jay Greguske <jgregusk@redhat.com>
# Copyright (C) 2013 Red Hat Inc.
# SPDX-License-Identifier:	GPL-2.0+

import logging
import math
from optparse import OptionParser
import os
import subprocess
import sys
import tempfile
import threading
import time

import fedora_ec2

#
# Constants
#
# we assume whatever account we're using has access to the same set of AMIs
amis = {
    'us-east-1':      {'i386': 'ami-e9ec2080', 'x86_64': 'ami-d9ed21b0'},
    'us-west-1':      {'i386': 'ami-3978247c', 'x86_64': 'ami-f1762ab4'},
    'us-west-2':      {'i386': 'ami-3c0a870c', 'x86_64': 'ami-3c0a870c'},
    'eu-west-1':      {'i386': 'ami-c9c4f6bd', 'x86_64': 'ami-69c5f71d'},
    'ap-southeast-1': {'i386': 'ami-08007a5a', 'x86_64': 'ami-2c007a7e'},
    'ap-southeast-2': {'i386': 'ami-a7b7209d', 'x86_64': 'ami-a7b7209d'},
    'ap-northeast-1': {'i386': 'ami-6aab1f6b', 'x86_64': 'ami-ea9723eb'},
    'sa-east-1':      {'i386': 'ami-3038e72d', 'x86_64': 'ami-3038e72d'}
}
results = {}
result_lock = threading.Lock()
mainlog = None

#
# Functions
#

def get_options():
    usage = """
    Create EBS-backed AMI from a disk image. The process begins by starting an
    instance creating an EBS volume and attaching it. The disk image is then
    dd'ed to the EBS volume on the instance over ssh. That volume is snapshoted
    and then registered as a new AMI. This script is threaded; one thread for
    each region we want to upload to. Usually, image file names are of the form:
    RHEL-X.Y-VariantName-Arch.raw

    Usage: %prog [options] path-to-image"""
    parser = OptionParser(usage=usage)
    parser.add_option('-a', '--arch', default=False,
        help='Override the arch. Normally this is parsed from the file name.')
    parser.add_option('-b', '--boot', help='Boot the EBS AMI afterward',
        action='store_true', default=False)
    parser.add_option('-d', '--debug', help='Print debug output', 
        action='store_true', default=False)
    parser.add_option('-D', '--diskimage', action='store_true', default=False,
        help='Upload a disk image rather than a partition image')
    parser.add_option('-k', '--keep', help='Keep tmp instance/volumes around',
        action='store_true', default=False)
    parser.add_option('-l', '--logdir', help='specify a directory for logs',
        default='.')
    parser.add_option('-n', '--name', default=False,
        help='Override the image name. The default is the disk image name.')
    parser.add_option('-q', '--quiet', help='Just print to logs, not stdout',
        action='store_true', default=False)
    parser.add_option('-r', '--region', action='append', default=[],
        help='Only upload to a specific region. May be used more than once.')
    opts, args = parser.parse_args()
    if len(args) != 1:
        parser.error('Please specify a path to an image')
    image = args[0]
    if not os.path.exists(image):
        parser.error('Could not find an image to upload at %s' % image)
    size = os.stat(image).st_size
    if not opts.diskimage:
        if os.getuid() != 0:
            parser.error('You have to be root to upload a partition image')
    opts.size = int(math.ceil(size / 1024.0 / 1024.0 / 1024.0))
    opts.cred = fedora_ec2.EC2Cred()
    if not opts.name:
        opts.name = os.path.basename(image)[:-4]
    if not opts.arch:
        if 'i386' in opts.name:
            opts.arch = 'i386'
        elif 'x86_64' in opts.name:
            opts.arch = 'x86_64'
        else:
            if 'i386' in os.path.basename(image):
                opts.arch = 'i386'
            elif 'x86_64' in os.path.basename(image):
                opts.arch = 'x86_64'
            else:
                parser.error('Unable to determine arch. Please use --arch')
    return opts, image

def setup_log(logdir='.', quiet=False, debug=False):
    """set up the main logger"""
    global mainlog
    format = logging.Formatter("[%(asctime)s %(name)s %(levelname)s]: %(message)s")
    logname = 'upload-ebs'
    if not os.path.exists(logdir):
        os.makedirs(logdir)
    mainlog = logging.getLogger(logname)
    if debug: 
        mainlog.setLevel(logging.DEBUG)
    else:
        mainlog.setLevel(logging.INFO)
    file_handler = logging.FileHandler(os.path.join(logdir, logname + '.log'))
    file_handler.setFormatter(format)
    mainlog.addHandler(file_handler)
    if not quiet:
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setFormatter(format)
        mainlog.addHandler(stdout_handler)

def run_cmd(cmd):
    """run an external command"""
    mainlog.debug('Command: %s' % cmd)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, shell=True)
    ret = proc.wait()
    output = proc.stdout.read().strip()
    mainlog.debug('Return code: %s' % ret)
    mainlog.debug('Output: %s' % output)
    if ret != 0:
        mainlog.error('Command had a bad exit code: %s' % ret)
        mainlog.error('Command run: %s' % cmd)
        mainlog.error('Output:\n%s' % output)
        raise fedora_ec2.Fedora_EC2Error('Command failed, see logs for output')
    return output, ret

def prep_part(image):
    """
    Use kpartx to mount a disk image and tweak grub.conf.
    Return the partition loopback for uploading later.
    """
    output, rc = run_cmd('/sbin/kpartx -a -v %s' % image)
    lines = output.split('\n')
    print lines
    loop = lines[0].split()[2]
    print loop
    time.sleep(3)
    mainlog.info('mounted disk image; partition available on %s' % loop)
    mapdev = os.path.join('/dev/mapper', loop)
    tmpdir = tempfile.mkdtemp(prefix='ebs-mnt-')
    run_cmd('/bin/mount %s %s' % (mapdev, tmpdir))
    mainlog.info('mount on %s' % tmpdir)
#    run_cmd("/bin/sed -i -e 's/(hd0,0)/(hd0)/' %s/boot/grub/menu.lst" %
    run_cmd("/bin/sed -i -e 's/(hd0,0)/(hd0)/' %s/boot/grub/grub.conf" %
        tmpdir)
    mainlog.info('tweaked menu.lst to boot as a partition')
    run_cmd('/bin/umount %s' % tmpdir)
    mainlog.warning('%s will no longer boot as a disk image' % image)
    return mapdev

def unmount_part(image):
    """clean up loopback droppings"""
    loop = os.path.basename(image)
    run_cmd('dmsetup remove %s' % loop)
    run_cmd('losetup -d /dev/%s' % loop[:loop.rindex('p')])
    mainlog.info('cleaned up loopback device pieces')

def upload_region(region, image_path, opts):
    """Upload an image to a region"""
    # start the Stager instance
    ec2 = fedora_ec2.EC2Obj(region=region, cred=opts.cred, debug=opts.debug,
        logfile=os.path.join(opts.logdir, 'rcm-%s.log' % region),
        quiet=opts.quiet)
    mainlog.info('beginning process for %s to %s' % (image_path, ec2.region))
    inst_info = ec2.start_ami(amis[ec2.region][opts.arch], wait=True)

    # create and attach volumes
    mainlog.info('[%s] creating EBS volume we will snapshot' % ec2.region)
    ebs_vol_info = ec2.create_vol(opts.size, wait=True)
    ebs_vol_info = ec2.attach_vol(inst_info['id'], ebs_vol_info['id'],
        wait=True)

    # prep the temporary volume and upload to it
    ec2.wait_ssh(inst_info)
    mainlog.info('[%s] uploading image %s to EBS volume' %
        (ec2.region, image_path))
    run_cmd('dd if=%s bs=4096 | ssh %s -C root@%s "dd of=%s bs=4096"' % 
        (image_path, ec2.get_ssh_opts(), inst_info['url'],
        ebs_vol_info['device']))

    # detach the two EBS volumes, snapshot the one we dd'd the disk image to,
    # and register it as an AMI
    ec2.detach_vol(inst_info['id'], ebs_vol_info['id'], wait=True)
    snap_info = ec2.take_snap(ebs_vol_info['id'], wait=True)
    new_ami = ec2.register_snap2(snap_info['id'], opts.arch, opts.name,
                                disk=opts.diskimage)

    # boot them if asked
    if opts.boot:
        ec2.start_ami(new_ami)

    # grant access to the new AMIs -- TBD

    # cleanup
    if not opts.keep:
        mainlog.info('[%s] cleaning up' % ec2.region)
        ec2.delete_vol(ebs_vol_info['id'])
        ec2.kill_inst(inst_info['id'])
    mainlog.info('%s is complete' % ec2.region)
    mainlog.info('[%s] AMI ID: %s' % (ec2.region, new_ami))

    # maintain results
    result_lock.acquire()
    results[new_ami] = '%s image for %s' % (ec2.region, opts.arch)
    result_lock.release()

if __name__ == '__main__':
    opts, ipath = get_options()
    setup_log(logdir=opts.logdir, quiet=opts.quiet, debug=opts.debug)
    if not opts.diskimage:
        ipath = prep_part(ipath)
    threads = []
    if len(opts.region) > 0:
        for region in opts.region:
            threads.append(threading.Thread(target=upload_region, 
                args=(region, ipath, opts), name=region))
    else:
        for region in amis.keys():
            threads.append(threading.Thread(target=upload_region, 
                args=(region, ipath, opts), name=region))
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    if not opts.diskimage:
        unmount_part(ipath)
    mainlog.info('Results of all uploads follow this line\n')
    mainlog.info('\n'.join(['%s : %s' % (k, v) for k, v in results.items()]))

