==================
Sigul Client Setup
==================

This document describes how to configure a sigul client. For more information
on sigul, please see `User:Mitr <User-Mitr>`_

Prerequisites
=============


#. Install ``sigul`` and its dependencies. It is available in both Fedora and EPEL:

   On Fedora:

   ::

        dnf install sigul

   On RHEL/CentOS (Using EPEL):

   ::

        yum install sigul

#. Ensure that your koji certificate and the Fedora CA certificates are
   present on the system that you're running the sigul client from at the
   following locations:

   * ``~/.fedora.cert``
   * ``~/.fedora-server-ca.cert``
   * ``~/.fedora-upload-ca.cert``

#. Admin privileges on koji are required to write signatures.
#. If you are running RHEL 6, add ``export NSS_HASH_ALG_SUPPORT=+MD5`` to your
   ``~/.bashrc.``

Configuration
=============

#. Run ``sigul_setup_client``
#. Choose a password for your NSS database. By default this will be stored on-disk in ``~/.sigul/client.conf``.
#. Choose an export password. You will only need to remember it until finishing
   ``sigul_setup_client``.
#. Enter the DB password you chose earlier, then the export password. You
   should see the message ``pk12util: PKCS12 IMPORT SUCCESSFUL``
#. Enter the DB password again. You should see the message ``Done``.
#. Assuming that you are running the sigul client within phx2, edit
   ``~/.sigul/client.conf`` to include the following lines: 

   ::
        [client]
        bridge-hostname: sign-bridge1
        server-hostname: sign-vault1


Configuration for Secondary Architectures
-----------------------------------------

All steps remain the same, however you will need admin privileges on your
secondary koji instance (not primary's). When editing ``~/sigul/client.conf``,
use:

::

    [client]
    bridge-hostname: secondary-signer
    server-hostname: secondary-signer-server

    [koji]
    # Config file used to connect to the Koji hub
    ; koji-config: ~/.koji/config
    # # Recognized alternative instances
    koji-instances: ppc s390 arm

    koji-config-ppc: /etc/koji/ppc-config
    koji-config-s390: /etc/koji/s390-config
    koji-config-arm: /etc/koji/arm-config


Updating your Fedora certificate
================================

When your Fedora certificate expires, after updating it run the following
commands:

::

    $ certutil -d ~/.sigul -D -n sigul-client-cert
    $ NSS_HASH_ALG_SUPPORT=+MD5 sigul_setup_client

.. _User-Mitr: https://fedoraproject.org/wiki/User:Mitr
