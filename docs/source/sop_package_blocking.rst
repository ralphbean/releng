================
Package Blocking
================

Description
===========
If a `package is removed from Fedora`_, for example because it was renamed, it
needs to be blocked in Koji. This prevents creating new package builds and
distribution of built RPMs. Packages are blocked in the listing of ``tags``,
due to inheritance it is enough to block packages at the oldest tag will make
it unavailable also in upstream tags.

Action
======

Perform the blocking
--------------------

Discover proper place to block
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The ticket should tell you which Fedora releases to block the package in.
Typically it'll say "Fedora 13", "F14" or rawhide.  This means we need to block
it at that Fedora level and all future tags.  However we do not block packages
in a Fedora release that has gone public unless.

The appropriate place to block a package is at the "f??" tag level (even for
rawhide, then the tag for the next release needs to be used, not the rawhide
tag).  This way the setting of block or not is inherited into future tags.

Performing the package block
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To block a package for a tag, use the ``block-pkg`` method of Koji.

::
    $ koji block-pkg --help
    Usage: koji block-pkg [options] tag package [package2 ...]
    (Specify the --help global option for a list of other help options)

    Options:
      -h, --help  show this help message and exit

For example, if we were asked to block python-psyco in Fedora 20 we would
issue:

::

    $ koji block-pkg f20 python-psyco

Now the ticket can be closed.

Tags for EPEL are named ``dist-5E-epel-build``, ``dist-6E-epel-build`` or
``epel7``.

EPEL Packages moved to RHEL
---------------------------
If a package moved to RHEL, it needs to be unblocked in the related build tag
to allow the RHEL package to be available in Koji:

::

    $ koji unblock-pkg dist-6E-epel-build foo

In case the package is only available on some architectures and a EPEL package
is still needed, the package must not be blocked but only all Fedora builds
need to be removed:

::

    $ koji untag-build --all dist-6E-epel foo

Verification
============
To verify that the package was successfully blocked use the ``list-pkgs`` koji
command:

::

    $ koji list-pkgs --show-blocked --package python-psyco

We should see the package listed as blocked:

::

    Package                 Tag                     Extra Arches     Owner          
    ----------------------- ----------------------- ---------------- ---------------
    python-psyco            f20                                      konradm         [BLOCKED]

We should not see it listed in any later Fedora tags.

Also the latest-pkg command should not return anything:

::

    $ koji latest-pkg dist-f8 hunspell-he
    Build                                     Tag                   Built by
    ----------------------------------------  --------------------  ----------------

Consider Before Running
=======================
* Don't block packages in a released Fedora.
* Make sure that you're being asked to block at the srpm level.  Blocking
  sub-packages cannot be done, but will happen naturally when the source
  package no longer builds the sub package.
* Watch the next day's rawhide/branched/whatever report for a slew of broken
  deps related to the package.  We may have to unblock the package in order to
  fix the deps. Check this with repoquery:

  ::

    $ repoquery -q --whatrequires --repoid <repo> <list of packages produced by this source rpm> --alldeps

  to catch binary dependencies and:

  ::

    repoquery -q --whatrequires --repoid <repo>-source --archlist src <list of packages produced by this source rpm> --alldeps

* Ensure that if the package is being renamed/replaced that proper Obsoletes/Provides are in place

.. _package is removed from Fedora:
    https://fedoraproject.org/wiki/How_to_remove_a_package_at_end_of_life
