========================
Deprecate FTBFS Packages
========================

Description
===========

.. note::
    FTBFS = "Fails To Build From Source"

Every release prior to the Feature Freeze we deprecate all packages that
`FTBFS`_. This keeps out software that no longer builds from source, and
prevents future problems down the road.

Action
======
The FTBFS process takes place in stages:

#. Detecting a list of FTBFS packages and the dependencies that will be broken
   if they are removed.
#. Sending the list of potential deprecated FTBFS packages to
   devel@lists.fedoraproject.org for community review and removal from the
   FTBFS list by fixing the package.
#. Removing packages confirmed as FTBFS from the Fedora package repositories.

Detecting FTBFS
---------------

We will remove packages that have failed to build for at least two release
cycles.  For example, in preparation for Fedora 21 branching, packages which
FTBFS since the Fedora 19 cycle (i.e. packages that have a dist tag of fc18 or
earlier) will be considered candidates for removal. Adjust `find_FTBFS.py`_
and run it to get a list of candidate packages.

Given a candidate list from above, rel-eng should attempt to build each of the
candidate packages using koji.  Should package building now succeed, the
package may be removed from the candidate list.

Announcing Packages to be Deprecated
------------------------------------

Email the output to the development list (``devel@lists.fedodraproject.org``)
at least a week before the feature freeze.  This gives maintainers an
opportunity to fix packages that are important to them. Follow-up on the list
where necessary.

Retiring FTBFS packages
-----------------------

Once maintainers have been given an opportunity to pick up and fix FTBFS
packages, the remaining packages are ``retired`` by blocking them, and creating
the ``dead.package`` file in git.

GIT and Package DB
^^^^^^^^^^^^^^^^^^
Required permissions: provenpackage for GIT, cvsadmin for Package DB.

We just have to remove the existing files from the ``master`` branch and
replace them with a ``dead.package`` file whose contents describe why the
package is dead. Also the package needs to be marked as retired in PackageDB.
Fedpkg takes care of this:

For example, if we wished to clean up git for the roxterm package we would:

::

    $ fedpkg clone roxterm
    $ cd roxterm
    $ fedpkg retire "Retired on $(date -I), because it failed to build for two releases (FTBFS Cleanup)."

Koji
^^^^

Required permissions: admin in koji if the automatic blocking fails.

Blocking should happen automatically a few minutes after the packags was
retired in PackageDB. If it does not, use the ``block-pkg`` ``koji`` command
is used to do the blocking.

Koji accepts multiple package names as input and thus we can use the FTBFS
package list as input.  Deprecated packages are only blocked from the latest
``f##`` tag.  For example, if we wanted to ``deprecate`` (block) ``sbackup,
roxterm,`` and ``uisp`` from rawhide during the development of Fedora 21 we
would run the following command: 

::

    $ koji block-pkg f21 sbackup roxterm uisp

Bugs
^^^^

This procedure probably leaves open bugs for the deprecated packages behind.
It is not within the scope of releng to take care of these. If bugs are closed,
only bugs targeted at Rawhide should be affected, since other branches might
still be maintained.

Verification
============
To verify that the packages were blocked correctly we can use the
``latest-pkg`` ``koji`` action.

::

    $ koji latest-pkg dist-f16 wdm

This should return nothing, as the ``wdm`` package is blocked.

Also check that package DB shows that the package is retired and that the
master branch contains only a dead.package file.

Consider Before Running
=======================

Generally we block anything that doesn't leave broken dependencies.  If there
are packages whose removal would result in broken dependencies a second
warning should be sent to devel@lists.fedoraproject.org and to
<package>-owner@fedoraproject.org for each dependent package.

Allow another couple of days for maintainers to take notice and fix these
package so the package repository can be maintained without broken
dependencies or needing to deprecate the package.  It is not good to have
broken package dependencies in our package repositories so every effort should
be made to find owners or to fix the broken dependencies.


.. _FTBFS: https://fedoraproject.org/wiki/Fails_to_build_from_source
.. _find_FTBFS.py: https://pagure.io/releng/blob/master/f/scripts/find_FTBFS.py
