.. _overview:

===================================
Fedora Release Engineering Overview
===================================

.. _overview-intro:

Introduction
============

The development of Fedora is a very open process, involving over a thousand
package maintainers (along with testers, translators, documentation writers
and so forth). These maintainers are responsible for the bulk of Fedora
distribution development. An elected `committee of people`_
provides some level of direction over the engineering aspects of the project.

The rapid pace of Fedora development leaves little time for polishing the
development system into a quality release. To solve this dilemma, the Fedora
project makes use of regular freezes and milestone (Alpha, Beta, Final)
releases of the distribution, as well as "branching" of our trees to maintain
different strains of development.

Stable branches of the Fedora tree and associated `Repositories`_ are
maintained for each Fedora release. The `Rawhide`_ rolling development tree
is the initial entry point for all Fedora development, and the trunk from
which all branches diverge. Releases are `Branched`_ from Rawhide some time
before they are sent out as stable releases, and the milestone releases
(Alpha, Beta and Final) are all built from this Branched tree.

Nightly snapshot images of various kinds are built from Rawhide and Branched
(when it exists) and made available for download from within the trees on the
`mirrors`_ or from the `Koji`_ build system. Many of these can be located via
the `release engineering dashboard`_.

The `Fedora Release Life Cycle`_ page is a good entry point for more details
on these processes. Some other useful references regarding the Fedora release
process include:

* The `Release planning process
  <https://fedoraproject.org/wiki/Changes/Policy>`_
* The `release validation test plan
  <https://fedoraproject.org/wiki/QA:Release_validation_test_plan>`_
* The `updates-testing process
  <https://fedoraproject.org/wiki/QA:Updates_Testing>`_, via
  `Bodhi <https://fedoraproject.org/wiki/Bodhi>`_ and the
  `Updates Policy <https://fedoraproject.org/wiki/Updates_Policy>`_
* The `test compose and release candidate system
  <https://fedoraproject.org/wiki/QA:SOP_compose_request>`_
* The `blocker bug process
  <https://fedoraproject.org/wiki/QA:SOP_blocker_bug_process>`_
  and
  `freeze exception bug process
  <https://fedoraproject.org/wiki/QA:SOP_freeze_exception_bug_process>`_
* The `Repositories`
* The `Bugzilla system
  <https://fedoraproject.org/wiki/Bugs_and_feature_requests>`_

Final Release Checklist
=======================

Various tasks need to be accomplished prior to a final Fedora release.
Release Engineering is responsible for many of them, as outlined here.

Export Approval
---------------

As a U.S. based company, Red Hat needs to file for export approval when
creating Fedora releases.  Currently this involves giving Red Hat Legal
a heads up at the final freeze date, and updating Legal once the final
tree has been spun.

Release Announcement
--------------------

The `Fedora Documentation Project`_ prepares release announcements for the
final releases.  A `bug needs to be filed`_ for this two weeks before the
final release date.

Mirror List Files
-----------------

A new set of mirror list files need to be created for the new release.
Email `Fedora Mirror Admins`_ to have these files created.  These should
be created at the Final Freeze point but may redirect to Rawhide until final
bits have been staged.

Release Composing
=================

Fedora “releases” can be built by anyone with a fast machine of proper arch
and access to a package repository.  All of the tools necessary to build a
release are available from the package repository. These tools aim to provide
a consistent way to build Fedora releases. A complete release can actually be
built with only a couple commands, including the creation of network install
images, offline install images ('DVDs'), live images, disk images, install
repositories, [[FedUp]] upgrade images, and other bits.
These commands are named pungi and livecd-creator.

.. note::
    There is work currently being done to replace livecd-creator with
    `livemedia-creator`_.

Pungi
-----

`Pungi`_ is the tool used to compose Fedora releases.  It requires being ran
in a chroot of the package set that it is composing.  This ensures that the
correct userland tools are used to match up with the kernel that will be used
to perform the installation.  It uses a comps file + yum repos to gather
packages for the compose.  The `Koji`_ build system provides a way to run
tasks within chroots on the various arches, as well as the ability to produce
yum repos of packages from specific collections.

Livecd-creator
--------------

Livecd-creator is part of the `livecd-tools`_ package in Fedora and it is used
to compose the live images as part of the Fedora release. It is also used to
compose many of the custom `Spins`_ or variants of Fedora.

Distribution
============

Once a compose has been completed, the composed tree of release media,
installation trees, and frozen `Repositories`_ needs to be synchronized with
the Fedora mirror system. [[MirrorManager]] has some more details on the
mirror system. Many of the images are also offered via BitTorrent as an
alternative method of downloading.

Download Mirrors
----------------

Depends on the Fedora Mirror System and infrastructure to populate them
privately.

BitTorrent
----------

BitTorrent is currently served by http://torrent.fedoraproject.org. Images are
added to the system via this `Standard Operating Procedure
<https://infrastructure.fedoraproject.org/infra/docs/torrentrelease.rst>`_.

Acknowledgements
================

This document was influenced by `release engineering documents
<http://www.freebsd.org/doc/en_US.ISO8859-1/articles/releng/article.html>`_
from `FreeBSD <http://freebsd.org>`_.

.. _committee of people: https://fedoraproject.org/wiki/Fedora_Engineering_Steering_Committee
.. _Repositories: https://fedoraproject.org/wiki/Repositories
.. _Rawhide: https://fedoraproject.org/wiki/Releases/Rawhide
.. _Branched: https://fedoraproject.org/wiki/Releases/Branched
.. _mirrors: https://mirrors.fedoraproject.org/
.. _Koji: https://fedoraproject.org/wiki/Koji
.. _release engineering dashboard: https://apps.fedoraproject.org/releng-dash/
.. _Fedora Release Life Cycle: https://fedoraproject.org/wiki/Fedora_Release_Life_Cycle
.. _Fedora Documentation Project: https://fedoraproject.org/wiki/Docs_Project
.. _bug needs to be filed:
    https://bugzilla.redhat.com/bugzilla/enter_bug.cgi?product=Fedora%20Documentation&op_sys=Linux&target_milestone=---&bug_status=NEW&version=devel&component=release-notes&rep_platform=All&priority=normal&bug_severity=normal&assigned_to=relnotes%40fedoraproject.org&cc=&estimated_time_presets=0.0&estimated_time=0.0&bug_file_loc=http%3A%2F%2F&short_desc=RELNOTES%20-%20Summarize%20the%20release%20note%20suggestion%2Fcontent&comment=Provide%20details%20here.%20%20Do%20not%20change%20the%20blocking%20bug.&status_whiteboard=&keywords=&issuetrackers=&dependson=&blocked=151189&ext_bz_id=0&ext_bz_bug_id=&data=&description=&contenttypemethod=list&contenttypeselection=text%2Fplain&contenttypeentry=&maketemplate=Remember%20values%20as%20bookmarkable%20template&form_name=enter_bug 
.. _Fedora Mirror Admins: mailto:mirror-admin@fedoraproject.org
.. _livemedia-creator: https://github.com/rhinstaller/lorax/blob/master/src/sbin/livemedia-creator
.. _Pungi: https://fedorahosted.org/pungi
.. _livecd-tools: https://fedoraproject.org/wiki/FedoraLiveCD
.. _Spins: https://spins.fedoraproject.org
