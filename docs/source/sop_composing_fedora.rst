================
Composing Fedora
================

Description
===========
When Quality Engineering requests a TC or RC they do so by filing or reopening
a ticket in Release Engineering trac. There is one trac ticket per milestone.

Action
======
Create the full product tree.

Composing the Tree
------------------
#. Log into a compose system: ``compose-x86-01`` or
   ``arm01-releng00.arm.fedoraproject.org``

   ::

        $ ssh -A compose-x86-01.phx2.fedoraproject.org

.. note::
    ssh agent forwarding is needed to enable sshing to boxes for composing the
    different arch trees.

#. update or checkout the git repo

   ::

        $ cd releng/
        $ git pull --rebase

   or

   ::

        $ git clone https://git.fedorahosted.org/git/releng

#. Sign rpms for bleed repo

   ::

        ssh releng04.phx2.fedoraproject.org

   repeat step 2 on signing box.

   ::

        $ cd releng/scripts
        $ NSS_HASH_ALG_SUPPORT=+MD5 ./sigulsign_unsigned.py fedora-22 -v --write-all <build nvrs>

#. Update the bleed repo on <code>compose-x86-01</code>:

   ::

        $ ~/releng/scripts/makebleed <build nvrs>

#. Kick off compose on a compose system: ``compose-x86-01`` or
   ``arm03-releng00.arm.fedoraproject.org``

   for a TC

   ::

        $ cd ~/releng/scripts
        $ ./run-pungi 22_Beta_TC9 "" 20150409

   for a RC

   ::

        $ cd ~/releng/scripts
        $ ./run-pungi 22_Beta _RC2 20150413

#. Check the compose

   check the tree under ``/mnt/fedora_koji/compose/<Compose>/<Release>/`` for
   completeness

#. open up the tree:

   ::

        sg releng "chmod 755 /pub/alt/stage/<Compose>/"

#. Close the ticket:

   Copy the output pasted at teh end of run-pungi and paste into the ticket and
   close it.

Update the ticket
-----------------
The ticket should be closed when the compose has been opened up pasting in the
output from run-pungi

Verification
============
Verification can be done as the task steps are being performed.

Image Creation
--------------
When pungi exits, you can verify that the ``development/<arch>/os/images/``
directory exists and has content.  That path is relative to the destination
directory you provide pungi.

Updating the Ticket
-------------------
One can click the link provided in the ticket update and ensure the path is
correct.  Verifying that the ticket is closed should be pretty self evident.

Consider Before Running
=======================
Many things can hinder a compose, broken deps in the chroot set, broken deps
in the compose set, bugs in the compose software, etc...  If any problem is ran
into along the way, it is best to alert QA via a ticket update, and then work
with the appropriate party to clear the obstruction.

Some of these tasks take a long time to finish, so it is highly recommended
that you run these tasks in a screen session.
