====================
Adding Build Targets
====================

Description
===========
Each new release we create a build target for the next release.  This SOP will
describe the steps necessary to prepare the new build target.

Action
======
Adding a build target is a complicated task.  It involves updating koji, git,
and fedora-release package.

.. _adding_build_targets_koji:

Koji
----
In koji a couple collection tags need to be made, and a target created to tie
them together.  We create a base collection tag named after the release, and
a build tag to hold a few things we use in the buildroots that are not part of
the distribution (glibc32/glibc64).  Inheritance to the previous release is
used for ownership and package data, as well as buildroot content data.

The ``add-tag``, ``add-tag-inheritance``, ``edit-tag``, and ``add-target``
commands are used.

::

    $ koji add-tag --help
    Usage: koji add-tag [options]  name
    (Specify the --help global option for a list of other help options)

    Options:
    -h, --help       show this help message and exit
    --parent=PARENT  Specify parent
    --arches=ARCHES  Specify arches


    $ koji add-tag-inheritance --help
    Usage: koji add-tag-inheritance [options]  tag parent-tag
    (Specify the --help global option for a list of other help options)

    Options:
    -h, --help            show this help message and exit
    --priority=PRIORITY   Specify priority
    --maxdepth=MAXDEPTH   Specify max depth
    --intransitive        Set intransitive
    --noconfig            Set to packages only
    --pkg-filter=PKG_FILTER
    Specify the package filter
    --force=FORCE         Force adding a parent to a tag that already has that
    parent tag

    $ koji edit-tag --help
    Usage: koji edit-tag [options] name
    (Specify the --help global option for a list of other help options)

    Options:
      -h, --help       show this help message and exit
      --arches=ARCHES  Specify arches
      --perm=PERM      Specify permission requirement
      --no-perm        Remove permission requirement
      --lock           Lock the tag
      --unlock         Unlock the tag
      --rename=RENAME  Rename the tag

    $ koji add-target --help
    Usage: koji add-target name build-tag <dest-tag>
    (Specify the --help global option for a list of other help options)

    Options:
    -h, --help  show this help message and exit

For example if we wanted to create the Fedora 17 tags, we would do the following:

::

    koji add-tag --parent f16-updates f17
    koji add-tag --parent f17 f17-updates
    koji add-tag --parent f17-updates f17-candidate
    koji add-tag --parent f17-updates f17-updates-testing
    koji add-tag --parent f17-updates-testing f17-updates-testing-pending
    koji add-tag --parent f17-updates f17-updates-pending
    koji add-tag --parent f17-updates f17-override
    koji add-tag --parent f17-override --arches=i686,x86_64 f17-build
    koji add-tag-inheritance --priority 1 f17-build f16-build
    koji edit-tag --perm=fedora-override f17-override
    koji edit-tag --lock f17-updates
    koji add-target f17 f17-build

.. note::
    The ``-pending`` tags are used by `Bodhi`_ and `Taskotron`_ to track and
    test proposed updates. These tags are not build targets and they don't get
    made into repos, so proper inheritance isn't vital.

Git
---

The pkgdb_sync_git_branches.py file which is hosted in Fedora Infrastructure
ansible (roles/distgit/templates/pkgdb_sync_git_branches.py) needs to be
updated for the new target for making branches.

Update ``BRANCHES`` with the new branch information. The branch name maps to
the branch that is its parent.

::

    BRANCHES = {'el4': 'master', 'el5': 'master', 'el6': 'f12',
            'OLPC-2': 'f7',
            'master': None,
            'fc6': 'master',
            'f7': 'master',
            'f8': 'master',
            'f9': 'master',
            'f10': 'master',
            'f11': 'master',
            'f12': 'master',
            'f13': 'master', 'f14': 'master'}


and update ``GITBRANCHES`` with the translation from pkgdb branch string to git
branch string:

::

    GITBRANCHES = {'EL-4': 'el4', 'EL-5': 'el5', 'EL-6': 'el6', 'OLPC-2': 'olpc2',
                   'FC-6': 'fc6', 'F-7': 'f7', 'F-8': 'f8', 'F-9': 'f9', 'F-10': 'f10',
                   'F-11': 'f11', 'F-12': 'f12', 'F-13': 'f13', 'F-14': 'f14', 'devel': 'master'}


The genacls.pkgdb file also needs to be updated for active branches to
generate ACLs for.  Update the ``ACTIVE`` variable.  genacls.pkgdb lives in
puppet (modules/gitolite/files/distgit/genacls.pkgdb). The format is pkgdb
branch string to git branch string (until pkgdb uses git branch strings):

::

    ACTIVE = {'OLPC-2': 'olpc2/', 'EL-4': 'el4/', 'EL-5': 'el5/',
              'EL-6': 'el6/', 'F-11': 'f11/', 'F-12': 'f12/', 'F-13': 'f13/',
              'F-14': 'f14/', 'devel': 'master'}

fedora-release
--------------
Currently the fedora-release package provides the ``%{?dist}`` definitions
used during building of packages.  When a new target is created,
fedora-release must be built for the collection with new dist definitions.

Comps
-----
* In the comps module in Fedora Hosted git
  (ssh://git.fedorarhosted.org/git/comps.git), create and add a new comps file
  based on the previous release. (Just copying it should be fine.) Add the new
  file to ``po/POTFILES.in``.
* When rawhide is retargeted in koji to point to the new release, update the
  ``Makefile`` to target comps-rawhide.xml at the new version.
* Don't forget to ``git push`` your changes after committing.

Verification
============
Given the complexity of all the changes necessary to create a new build target,
the best way to verify is to attempt a build.  Given that fedora-release has to
be built before anything else so that dist tags translate correctly it is a
good test case.  For example, this was used to test the new Fedora 15 target:

* Use pkgdb to request an F-15 branch of fedora-release
* Use pkgdb2branch.py to actually make the branch
* Update fedora-release clone
* Adjust .spec file in master for new dist defines
* commit/build
* Track build in koji to ensure proper tagging is used

What this won't test is translations of dist at tag time given that
``fedora-release`` doesn't use dist in it's Release.  Verifying with a second
package that uses dist is a good idea.

.. _Bodhi: https://fedoraproject.org/wiki/Bodhi
.. _Taskotron: https://fedoraproject.org/wiki/Taskotron
