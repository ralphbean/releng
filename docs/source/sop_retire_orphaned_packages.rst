========================
Retire Orphaned Packages
========================

Description
===========

Every release prior to the `Feature Freeze/Branching`_ Release Engineering
retires `orphaned packages`_. This keeps out unowned software and prevents
future problems down the road.

Action
======
The orphan process takes place in stages:

#. Detecting a list of orphans and the dependencies that will be broken if the
   orphans are removed.
#. Sending the list of potential orphans to devel@lists.fedoraproject.org for
   community review and removal from the orphan list.
#. Retriring packages nobody wants to adopt.

Detecting Orphans
-----------------

A script called ``find_unblocked_orphans.py`` assists in the detection process.
It should be run on a machine that has ``koji`` and ``python-fedora``
installed. It runs without options and takes a while to complete.

``find_unblocked_orphans.py`` is available in the `Release Engineering git
repository`_

Announcing Packages to be retired
---------------------------------

``find_unblocked_orphans.py`` outputs text to stdout on the command line in a
form suitable for the body of an email message.

::

    $ ./find-unblocked-orphans.py > email-message

Email the output to the development list (``devel@lists.fedodraproject.org``)
at least a month before the feature freeze, send mails with updated lists as
necessary.  This gives maintainers an opportunity to pick up orphans that are
important to them or are required by other packages.

Retiring Orphans
----------------

Once maintainers have been given an opportunity to pick up orphaned packages,
the remaining `packages are retired`_

Bugs
^^^^
This procedure probably leaves open bugs for the d packages behind. It is not
within the scope of releng to take care of these. If bugs are closed, only bugs
targeted at Rawhide should be affected, since other branches might still be
maintained.

Verification
============
To verify that the packages were blocked correctly we can use the ``latest-pk`` ``koji`` action.

::

    $ koji latest-pkg dist-f21 wdm

This should return nothing, as the ``wdm`` package is blocked.

Consider Before Running
=======================
Generally we retire anything that doesn't leave broken dependencies.  If there
are orphans whose removal would result in broken dependencies a second warning
should be sent to ``devel@lists.fedoraproject.org`` and to
``<package>-owner@fedoraproject.org`` for each dependent package.

Allow another couple of days for maintainers to take notice and fix these
package so the package repository can be maintained without broken dependencies
or needing to  the package.  It is not good to have broken package dependencies
in our package repositories so every effort should be made to find owners or to
fix the broken dependencies.

.. _Feature Freeze/Branching: https://fedoraproject.org/wiki/Schedule
.. _orphaned packages:
    https://fedoraproject.org/wiki/Orphaned_package_that_need_new_maintainers
.. _Release Engineering git repository: https://pagure.io/releng
.. _packages are retired:
    https://fedoraproject.org/wiki/How_to_remove_a_package_at_end_of_life
