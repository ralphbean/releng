#!/usr/bin/python -tt

import glob
import os
import subprocess
import sys
import time
import unittest

import fedora_ec2

class TestFedora_EC2(unittest.TestCase):

    def setUp(self):
        """Run before each test; create an EC2Obj for us to work with"""
        self.cred = fedora_ec2.EC2Cred()
        self.ec2 = fedora_ec2.EC2Obj('US', cred=self.cred, debug=True, quiet=False)
        if self.cred.account != '125523088429':
            raise RuntimeError('You can only test with the fedaws account')
        self.keypair = 'releng-us-east'     # this should exist in us-east
        self.test_ami = 'ami-e291668b'      # this too
        self.test_vol = 'vol-ff185494'      # and this
        self.instances = []
        self.volumes = []

    def test_obj_conf(self):
        """test if EC2Obj optional parameters function"""
        # We don't know what the id is because EC2Objs are created for each
        # test case, and we don't know that ordering.
        id = self.ec2.id
        ec2_1 = fedora_ec2.EC2Obj('US', cred=self.cred, quiet=True)
        ec2_2 = fedora_ec2.EC2Obj('us-west-1', cred=self.cred, quiet=True)
        ec2_3 = fedora_ec2.EC2Obj('EU', quiet=True, debug=True, logfile='test.log')
        ec2_4 = fedora_ec2.EC2Obj('ap-southeast-1', quiet=True)
        ec2_5 = fedora_ec2.EC2Obj('ap-northeast-1', quiet=True)
        self.assertEqual(ec2_1.id, id + 1)
        self.assertEqual(ec2_2.id, ec2_1.id + 1)
        self.assertEqual(ec2_3.id, ec2_2.id + 1)
        self.assertEqual(ec2_4.id, ec2_3.id + 1)
        self.assertEqual(ec2_5.id, ec2_4.id + 1)
        self.assertEqual(ec2_1.region, 'us-east-1')
        self.assertEqual(ec2_2.region, 'us-west-1')
        self.assertEqual(ec2_3.region, 'eu-west-1')
        self.assertEqual(ec2_4.region, 'ap-southeast-1')
        self.assertEqual(ec2_5.region, 'ap-northeast-1')
        files = os.listdir('.')
        self.assertTrue('test.log' in files)
        self.assertTrue('fedora_ec2.%s.log' % id in files)
        self.assertEqual(ec2_3.cred.account, self.cred.account)
        os.remove('test.log')

    def test_pvgrub(self):
        """test pvgrub-specific code"""
        self.assertEqual(fedora_ec2.get_pvgrub(True, False, 'us-east-1',
            'i386'), 'aki-407d9529')
        self.assertEqual(fedora_ec2.get_pvgrub(True, False, 'us-east-1',
            'x86_64'), 'aki-427d952b')
        #self.assertRaises(fedora_ec2.Fedora_EC2Error, 
        #    fedora_ec2.get_pvgrub(True, True, 'fake', 'ppc64'))

    def test_regions(self):
        """test region specific methods"""
        self.assertEqual(self.ec2.alias_region('US'), 'us-east-1')
        self.assertEqual(self.ec2.alias_region('us-east'), 'us-east-1')
        self.assertEqual(self.ec2.alias_region('us-west'), 'us-west-1')
        self.assertEqual(self.ec2.alias_region('EU'), 'eu-west-1')
        self.assertEqual(self.ec2.alias_region('eu-west'), 'eu-west-1')
        self.assertEqual(self.ec2.alias_region('us-east-1'), 'us-east-1')
        self.assertEqual(self.ec2.alias_region('us-west-1'), 'us-west-1')
        self.assertEqual(self.ec2.alias_region('eu-west-1'), 'eu-west-1')
        self.assertEqual(self.ec2.alias_region('ap-southeast'), 
                         'ap-southeast-1')
        self.assertEqual(self.ec2.alias_region('ap-southeast-1'), 
                         'ap-southeast-1')
        self.assertEqual(self.ec2.alias_region('ap-northeast'), 
                         'ap-northeast-1')
        self.assertEqual(self.ec2.alias_region('ap-northeast-1'), 
                         'ap-northeast-1')
        self.assertEqual(self.ec2.alias_region('fake'), 'fake')

    def test_internals(self):
        """test internal methods that consumers should not use"""
        inst = 'i-47faec2d'     # this doesn't really exist
        vol = 'vol-3aa69553'    # nor this
        dev_a = self.ec2._take_dev(inst, vol)
        self.assertTrue(dev_a.startswith('/dev/sd'))
        self.assertEqual(self.ec2._att_devs[inst][dev_a], vol)
        dev_b = self.ec2._release_dev(inst, vol)
        self.assertEqual(dev_a, dev_b)
        for dev in fedora_ec2.EC2Obj._devs.keys():
            self.assertEqual(self.ec2._att_devs[inst][dev], None)
        self.assertRaises(fedora_ec2.Fedora_EC2Error, self.ec2._release_dev, inst, 
                          vol)
        for d in range(9):
            self.ec2._take_dev(inst, vol[:-1] + str(d))
        self.assertRaises(fedora_ec2.Fedora_EC2Error, self.ec2._take_dev, inst, vol)

    def test_ami_methods(self):
        """test methods that manipulate AMIs"""
        self.assertRaises(fedora_ec2.Fedora_EC2Error, self.ec2.ami_info, 'fake')
        ami_info = self.ec2.ami_info(self.test_ami)
        self.assertEqual(ami_info['id'], self.test_ami)
        self.assertEqual(ami_info['owner'], '125523088429')
        self.assertEqual(ami_info['visibility'], 'public')
        self.assertEqual(ami_info['arch'], 'x86_64')
        self.assertEqual(ami_info['status'], 'available')
        self.assertEqual(ami_info['type'], 'machine')
        self.assertEqual(ami_info['aki'], 'aki-427d952b')
        self.assertEqual(ami_info['ari'], ' ')

        # de-registration is checked in test_snapshot_methods

    def test_inst_methods(self):
        """test the methods that interact with an instance"""
        inst_info = self.ec2.start_ami(self.test_ami, zone='us-east-1c',
            group='Basic')
        self.instances.append(inst_info['id'])
        self.assertTrue(inst_info['id'].startswith('i-'))
        self.assertEqual(inst_info['ami'], self.test_ami)
        self.assertEqual(inst_info['status'], 'pending')
        self.assertEqual(inst_info['zone'], 'us-east-1c')
        self.assertEqual(inst_info['group'], 'Basic')
        new_info = self.ec2.inst_info(inst_info['id'])
        for attr in ('id', 'ami', 'type', 'zone', 'time', 'aki', 'ari',
            'group', 'time'):
            self.assertEqual(inst_info[attr], new_info[attr])
        self.assertRaises(fedora_ec2.Fedora_EC2Error, self.ec2.wait_inst_status,
            new_info['id'], 'zomg', tries=3, interval=1)
        new_info = self.ec2.wait_inst_status(new_info['id'], 'running')
        self.assertEqual(new_info['status'], 'running')
        self.assertEqual(new_info['id'], inst_info['id'])
        new_info = self.ec2.kill_inst(new_info['id'], wait=True)
        self.instances.pop()
        self.assertEqual(new_info['id'], inst_info['id'])
        self.assertEqual(new_info['status'], 'terminated')

    def test_vol_methods(self):
        """test methods that work with volumes"""
        zone = 'us-east-1c'
        size = ' 20'
        inst_info = self.ec2.start_ami(self.test_ami, zone=zone, wait=True)
        self.instances.append(inst_info['id'])
        vol_info = self.ec2.create_vol(size, zone, wait=True)
        self.volumes.append(vol_info['id'])
        self.assertEqual(vol_info['size'], size)
        self.assertEqual(vol_info['zone'], zone)
        self.assertRaises(fedora_ec2.Fedora_EC2Error, self.ec2.wait_vol_status,
            vol_info['id'], 'zomg', tries=3, interval=1)
        new_info = self.ec2.wait_vol_status(vol_info['id'], 'available')
        self.assertEqual(new_info['id'], vol_info['id'])
        self.assertEqual(new_info['status'], 'available')
        self.assertRaises(fedora_ec2.Fedora_EC2Error, self.ec2.attach_vol,
            inst_info['id'], new_info['id'], dev='fake')
        att_info = self.ec2.attach_vol(inst_info['id'], new_info['id'],
            wait=True)
        self.assertEqual(att_info['attach_status'], 'attached')
        self.assertEqual(att_info['id'], vol_info['id'])
        self.assertEqual(att_info['instance'], inst_info['id'])
        self.assertRaises(fedora_ec2.Fedora_EC2Error, self.ec2.vol_info, 'fake')
        self.assertRaises(fedora_ec2.Fedora_EC2Error, self.ec2.attach_vol,
            att_info['instance'], att_info['id'])
        new_info = self.ec2.detach_vol(att_info['instance'], att_info['id'],
            wait=True)
        self.assertEqual(new_info['status'], 'available')
        del_id = self.ec2.delete_vol(new_info['id'])
        self.assertTrue(del_id, new_info['id'])
        self.volumes.pop()
        self.ec2.kill_inst(inst_info['id'])
        self.instances.pop()

    def test_snapshot_methods(self):
        """test methods that handle volume snapshots"""
        snap_info = self.ec2.take_snap(self.test_vol, wait=True)
        self.assertEqual(snap_info['vol_id'], self.test_vol)
        self.assertEqual(snap_info['status'], 'completed')
        ami_id = self.ec2.register_snap2(snap_info['id'], 'x86_64', 'Test')
        self.assertTrue(ami_id.startswith('ami-'))
        self.assertRaises(fedora_ec2.Fedora_EC2Error, self.ec2.delete_snap,
            snap_info['id'])
        self.ec2.deregister_ami(ami_id)
        del_id = self.ec2.delete_snap(snap_info['id'])
        self.assertEqual(del_id, snap_info['id'])

    def tearDown(self):
        """Run after each test; remove log files we created"""
        [os.remove(log) for log in glob.glob('fedora_ec2.*.log')]
        # we try to clean up after ourselves if something failed
        for inst in self.instances:
            subprocess.Popen('ec2-terminate-instances %s' % inst, 
                stdout=subprocess.PIPE, close_fds=True, 
                stderr=subprocess.STDOUT, shell=True)
        for vol in self.volumes:
            subprocess.Popen('ec2-delete-volume %s' % inst, 
                stdout=subprocess.PIPE, close_fds=True, 
                stderr=subprocess.STDOUT, shell=True)

if __name__ == '__main__':
    unittest.main()
