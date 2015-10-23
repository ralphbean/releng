=============================
Adding a New Release Engineer
=============================

Description
===========
People volunteer (or get assigned) to doing Fedora release engineering from
time to time.  This SOP seeks to describe the process to add a new release
engineer so that they have the rights to accomplish their tasks, know where
to find the tasks, and are introduced to the existing members. There are
several groups that manage access to the respective systems:

* ``cvsadmin``: Admin group for pkgdb2 (allows to retire/orphan all packages
  etc), allows git write access via SSH to all packages in dist-git
* ``gitreleng``: Allows write access to release engineering git repo
* ``signers``: Membership is necessary to use `sigul`_.
* ``sysadmin``: Allows SSH access to bastion, the SSH gateway to the PHX2 data
  center. SSH access to several other internal systems is only possible from
  here.
* ``sysadmin-cvs``: Allows shell access to pkgs01 (pkgs.fedoraproject.org)
* ``sysadmin-releng``: Allows SSH access to autosign01, koji03, koji04,
  releng04, relepel01 from bastion

Action
======
A new release engineer will access rights in a variety of systems, as well as
be introduced to the releng group.

Git
---
Fedora Release Engineering maintains a git repo of scripts.  This can be found
in `Pagure`_ at ssh://git@pagure.io/releng.git.  Write access to this group is
controlled by access to the 'gitreleng' FAS group.  The new member's FAS
username will need to be added to this group.

https://pagure.io/releng


``FIXME: walkthrough group addition``

FAS
---
There is a releng group in FAS that release engineers are added to in order to
grant them various rights within the Fedora infrastructure.  The new member's
FAS username will need to be added to this group.

``FIXME: walkthrough group addition``

Koji
----
In order to perform certain (un)tagging actions a release engineer must be an
admin in koji.  To grant a user admin rights one uses the ``grant-permission``
command in koji.

::

    $ koji grant-permission --help
    Usage: koji grant-permission <permission> <user> [<user> ...]
    (Specify the --help global option for a list of other help options)

    Options:
      -h, --help  show this help message and exit

For example if we wanted to grant npetrov admin rights we would issue:

::

    $ koji grant-permission admin npetrov

Sigul
-----
Sigul is our signing server system.  They need to bet setup as a signer if
they are going to be signing packages for a release.

For information on how to setup Sigul, please see: `sigul`_

RelEng Docs Page
----------------
The new release engineer should be added to the
ref:`Release Engineering membership list <index-team-composition>`_

rel-eng email list
------------------
Release engineering ticket spam and discussion happens on our `Mailing List`_.
New releng people need to subscribe.

IRC
---
We ask that release engineers idle in `#fedora-releng` on Freenode to be
available for queries by other infrastructure admins. Idling on `#fedora-admin`
on Freenode is optional. It is noisy little bit but people sometimes ask
releng stuff.

New member announcement
-----------------------
When a new releng member starts, we announce it to the email list.  This lets
the other admins know to expect a new name to show up in tickets and on IRC.

Verification
============

Git
---
You can verify group membership by sshing to a system that is setup with FAS
and using ``getent`` to verify membership in the gitreleng group:

::

    $ ssh fedorapeople.org getent group gitreleng
    gitreleng:x:101647:ausil,dwa,jwboyer,kevin,notting,pbabinca,sharkcz,skvidal,spot

You can verify that the new user is in the above list.

FAS
---
You can verify group membership by sshing to a system that is setup with FAS
and using ``getent`` to verify membership in the releng group:

::

    $ ssh fedorapeople.org getent group releng
    releng:x:101737:atowns,ausil,dwa,jwboyer,kevin,lmacken,notting,pbabinca,spot

You can verify that the new user is in the above list.

Koji
----
To verify that the releng member is an admin koji use the ``list-permissions``
koji command:

::

    $ koji list-permissions --user npetrov
    admin

This shows that npetrov is an admin.

Sigul
-----
* ``FIXME``

Wiki Page
---------
Verification is easy.  Just look at the page.

releng mailing list
-------------------
Verify by asking the user if they got the announcement email

Announcement email
------------------
See above

Consider Before Running
=======================
* Make sure the releng person has a solid grasp of the tasks we do and where
  to get help if stuck

.. _sigul: https://fedoraproject.org/wiki/Sigul_Client_Setup_SOP
.. _Pagure: https://pagure.io/pagure
.. _Mailing List: https://admin.fedoraproject.org/mailman/listinfo/rel-eng
