=======================
Release Package Signing
=======================

Description
===========
For each of Fedora's public releases (Alpha, Beta, and Final) it is Release
Engineering's responsibility to sign all packages with Fedora's GPG key. This
provides confidence to Fedora's users about the authenticity of packages
provided by Fedora.

The :doc:`/sop_create_release_signing_key` document explains the process for
creating the GPG key used.

Consider Before Running
=======================

This script takes a very long time to run, as much as 4 or 5 days, so it needs
to be started well in advance of when you need the packages all signed.

Signing all the packages will cause a lot of churn on the mirrors, so expect
longer than usual compose and rsync times, as well as potential issues with
proxies as file contents change but the name remains the same.

Action
======
#. Log into a system with ``sigul`` and start a ``screen`` or ``tmux`` session.
   The signing process takes a long time--screen allows the process to continue
   if you session gets disconnected.

   ::

        $ screen -S sign

   or

   ::

        $ tmux new -s sign

#. Check out the Release Engineering ``git`` repo

   ::
        $ git clone git://git.fedorahosted.org/git/releng

#. Change directories to the ``scripts`` directory to execute
   ``sigulsign_unsigned.py``.

   For example, to sign everything for Fedora 13 Alpha we would issue:

   ::
        $ ./sigulsign_unsigned.py -vv --tag dist-f13 fedora-13

   This signs the packages with verbose output so you can track progress
   incrementally.

Verification
============
Once the signing is done, use ``rpmdev-checksig`` to verify that a package has
been signed.  You can use the output of a recent rawhide compose to test.  In
this example we use a released Fedora 12 package:

::

    $ rpmdev-checksig /pub/fedora/linux/releases/12/Everything/i386/os/Packages/pungi-2.0.20-1.fc12.noarch.rpm 
    /pub/fedora/linux/releases/12/Everything/i386/os/Packages/pungi-2.0.20-1.fc12.noarch.rpm: MISSING KEY - 57bbccba

This output shows that the apckage was signed with key ``57bbccba``, and that
this key does not exist in your local rpm database. If the key did exist in the
local rpm database it's likely there would be no output so it's best to run
this on a system that does not have gpg keys imported.

