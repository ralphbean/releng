==============
Mass Branching
==============

Description
===========

At each alpha freeze we branch the pending release away from ``devel/`` which
allows rawhide to move on while the pending release goes into bugfix and
polish mode.

Action
======

PackageDB
---------

Mass branching in the pkgdb is the first step. It should be done near the time
that the scm branches are created so as not to confuse packagers.  However, it
does not cause an outage so it could be done ahead of time.

The action on pkgdb is in 3 steps:

#. Edit the dist-tag of master collection] in PackageDB,
#. Create the new collection via the `Admin interface of pkgdb`_, for Fedora
   Branched the status should be set to ``Under Development`` until the `Final
   Freeze`_ is reached. This allows to retire packages until then.
#. Finally, on one of the pkgdb host (ie: pkgdb01 or pkgdb02 or pkgdb01.stg if
   you want to try on staging first), call the script pkgdb2_branch.py:

   ::

        sudo pkgdb2_branch.py f21 --user=<fas_user> --groups=<fas_group_allowed>

   ``fas_user`` corresponds to the FAS username of the admin doing the action.

   ``fas_group_allowed`` corresponds to a FAS group allowed to perform admin
   actions (ie: ADMIN_GROUP in the `pkgdb configuration file`_)

The mass branch process starts on the server and will last for ~1h45

When the branching is finished, the email address defined at MAIL_ADMIN in the
configuration file will receive an email that tells which were branched and
which were unbranched.

If something fails spectacularly, it is safe to try mass branching again at a
later time.  If only a few cleanups a re needed it might be better to do that
with the regular branch commands.

Puppet
-------

.. note::
    FIXME: This needs updating, puppet is no longer a thing in Fedora Infra

A couple files under puppet management need to be updated to be aware of a new branch.

pkgdb2branch.py
^^^^^^^^^^^^^^^

This file is used by an scmadmin to read data from pkgdb and create branches
in the source control.  Two parts need to be updated, one part that defines
valid branches and what existing branch to create them from, and the other
part defines a mapping of branch names in pkgdb to branch names in scm.

On the puppet server in a clone edit the
``modules/gitolite/files/distgit/pkgdb2branch.py`` file:

::

    diff --git a/modules/gitolite/files/distgit/pkgdb2branch.py b/modules/gitolite/file
    index ce79467..c40e83c 100755
    --- a/modules/gitolite/files/distgit/pkgdb2branch.py
    +++ b/modules/gitolite/files/distgit/pkgdb2branch.py
    @@ -29,14 +29,15 @@ BRANCHES = {'el4': 'master', 'el5': 'master', 'el6': 'f12',
             'f11': 'master',
             'f12': 'master',
             'f13': 'master',
    -        'f14': 'master'}
    +        'f14': 'master',
    +        'f15': 'master'}

     # The branch names we get out of pkgdb have to be translated to git
     GITBRANCHES = {'EL-4': 'el4', 'EL-5': 'el5', 'EL-6': 'el6', 'OLPC-2': 'olpc2',
                    'FC-6': 'fc6', 'F-7': 'f7', 'F-8': 'f8', 'F-9': 'f9',
                    'F-10': 'f10', 'OLPC-3': 'olpc3',
                    'F-11': 'f11', 'F-12': 'f12', 'F-13': 'f13', 'f14': 'f14',
    -               'devel': 'master'}
    +               'f15': 'f15', 'devel': 'master'}

genacls.pkgdb
^^^^^^^^^^^^^

The other file is ran by cron that will read data out of pkgdb and construct an
ACL config file for our scm.  It has a section that lists active branches to
deal with as pkgdb will provide data for all branches.

Again on the puppet server in a clone:
``modules/gitolite/files/distgit/genacls.pkgdb``

::

    diff --git a/modules/gitolite/files/distgit/genacls.pkgdb b/modules/gitolite/files/
    index e531dc2..07b2ba7 100755
    --- a/modules/gitolite/files/distgit/genacls.pkgdb
    +++ b/modules/gitolite/files/distgit/genacls.pkgdb
    @@ -22,7 +22,7 @@ if __name__ == '__main__':
         ACTIVE = {'OLPC-2': 'olpc2/', 'OLPC-3': 'olpc3/', 'EL-4': 'el4/',
                   'EL-5': 'el5/', 'EL-6': 'el6/', 'F-11': 'f11/',
                   'F-12': 'f12/', 'F-13': 'f13/', 'f14': 'f14/',
    -              'devel': 'master'}
    +              'f15': 'f15/', 'devel': 'master'}

         # Create a "regex"ish list 0f the reserved branches

fedora-packages
^^^^^^^^^^^^^^^

There is a file in the fedora-packages webapp source that needs to be updated
with new releases.  It tells fedora-packages what tags to ask koji about. Just
like before, make the following edit in puppet in a clone:

::

    diff --git a/modules/packages/files/distmappings.py b/modules/packages/files/distmappings.py
    index c72fd4b..b1fbaa5 100644
    --- a/modules/packages/files/distmappings.py
    +++ b/modules/packages/files/distmappings.py
    @@ -1,5 +1,9 @@
     # Global list of koji tags we care about
    -tags = ({'name': 'Rawhide', 'tag': 'f20'},
    +tags = ({'name': 'Rawhide', 'tag': 'f21'},
    +
    +        {'name': 'Fedora 20', 'tag': 'f20-updates'},
    +        {'name': 'Fedora 20', 'tag': 'f20'},
    +        {'name': 'Fedora 20 Testing', 'tag': 'f20-updates-testing'},
     
             {'name': 'Fedora 19', 'tag': 'f19-updates'},
             {'name': 'Fedora 19', 'tag': 'f19'},
    @@ -13,10 +17,6 @@ tags = ({'name': 'Rawhide', 'tag': 'f20'},
             {'name': 'Fedora 17', 'tag': 'f17'},
             {'name': 'Fedora 17 Testing', 'tag': 'f17-updates-testing'},
     
    -        {'name': 'Fedora 16', 'tag': 'f16-updates'},
    -        {'name': 'Fedora 16', 'tag': 'f16'},
    -        {'name': 'Fedora 16 Testing', 'tag': 'f16-updates-testing'},
    -
             {'name': 'EPEL 6', 'tag': 'dist-6E-epel'},
             {'name': 'EPEL 6', 'tag': 'dist-6E-epel-testing'},

Push the changes
^^^^^^^^^^^^^^^^

When done editing the files, commit and push them, then restart puppet on the
scm server in order to get the new files in place.

SCM
---

The following work is performed on pkgs01

Make git branches
^^^^^^^^^^^^^^^^^
Run pkgdb2branch.py to branch the repos on the scm server.  The
``--branch-for`` option was designed with this use case in mind:

::

    ./pkgdb2branch.py --branch-for=f15

If for some reason that doesn't work, you can try this alternative:

::

    cat pkglist.txt|./pkgdb2branch.py -c -

where ``pkglist.txt`` is a list of all the packages to branch.

Update ACLs
^^^^^^^^^^^

Although cron may have run, it is smart to manually run the cron job to make
sure new ACLs are in place:

::

    $ sudo -u jkeating /usr/local/bin/genacls.sh

Taskotron
---------
`File a Taskotron ticket`_ and ask for the newly branched release support to
be added. (Log in to Phabricator using your FAS_account@fedoraproject.org
email address).

Koji
----
The koji build system needs to have some tag/target work done to handle builds
from the new branch and to update where builds from master go. See the 
:ref:`section on Koji in the Adding Build Targets SOP <adding_build_targets_koji>`
for details.

Fedora Release
--------------
The Fedora release package needs to be updated in both the new branch and in
master.

.. note::
    FIXME Link to fedora release bump SOP ... FIXME Does that SOP exist?

Bodhi
-----
Bodhi needs to be turned on for the new branch. Instructions in the `Bodhi SOP`_

Enable nightly branched compose
-------------------------------
A cron job needs to be modified and turned on for the new branch.

.. note::
    FIXME Link to nightly branched SOP ... Does that SOP exist?

Update kickstart used by nightly live ISOs
------------------------------------------

On a nightly basis, a live ISO image is created for each `spin`_ and hosted at
http://alt.fedoraproject.org/pub/alt/nightly-composes.  The `dnf`_/`yum`_
repositories used by  `spin-kickstarts`_ need to be updated to use the branched
repository.  Please `file a rel-eng ticket`_ to request updating the kickstart
file used to generate the nightly spin ISO's.

Comps
-----
A new comps file needs to be created for the next fedora release (the one after
what we just branched for). 

Please see :doc:`sop_updating_comps`

Mock
----
Mock needs to be updated to have configs for the new branch.  This should
actually be done and pushed just before the branch event.

.. note::
    FIXME Link to mock update SOP ... does that exist?

MirrorManager
-------------
Mirror manager will have to be updated so that the `dnf`_/`yum`_ repo
redirections are going to the right places. 

.. note::
    FIXME Link to MM SOP ... exists?

Getting a List of Unbranched Packages
=====================================

.. note::
    FIXME: This section is deprecated and needs a replacement

After mass branching you may want to run sanity checks to see if there were
packages that weren't successfully branched.  There's a script on the cvs
server that can help you do this.  The script needs to be run first on the
cvs server and then on a machine with the kojiclient libraries installed
(your local workstation should be fine.).


On cvs1:

::

    CVSROOT=/pkgs/cvs cvs co CVSROOT
    CVSROOT/admin/find-unbranched cvs F-12 > unbranched

On your workstation:

::

    scp cvs1.fedoraproject.org:CVSROOT/admin/find-unbranched .
    scp cvs1.fedoraproject.org:unbranched .
    ./find-unbranched compare F-12 unbranched

Update critpath
---------------

Packagedb has information about which packages are critpath and which are not.
A script that reads the `dnf`_/`yum`_ repodata (critpath group in comps, and
the package dependencies) is used to generate this.  Read
:doc:`sop_update_critpath` for the steps to take.

Consider Before Running
=======================

.. note::
    FIXME: Need some love here

.. _master collection: https://admin.fedoraproject.org/pkgdb/collection/master/
.. _Admin interface of pkgdb: https://admin.fedoraproject.org/pkgdb/admin/
.. _Final Freeze: https://fedoraproject.org/wiki/Schedule
.. _pkgdb configuration file:
    https://infrastructure.fedoraproject.org/infra/ansible/roles/pkgdb2/templates/pkgdb2.cfg
.. _File a Taskotron ticket:
    https://phab.qadevel.cloud.fedoraproject.org/maniphest/task/create/?projects=PHID-PROJ-prgpoumlmfdczdr4dyv3
.. _Bodhi SOP: https://infrastructure.fedoraproject.org/infra/docs/bodhi.rst
.. _spin: http://spins.fedoraproject.org
.. _dnf: https://fedoraproject.org/wiki/Dnf
.. _yum: https://fedoraproject.org/wiki/Yum
.. _spin-kickstarts: https://fedorahosted.org/spin-kickstarts/
.. _file a rel-eng ticket: 
    https://fedorahosted.org/rel-eng/newticket?summary=Update%20nightly%20spin%20kickstart&type=task&component=production&priority=critical&milestone=Hot%20issues&cc=kevin 
