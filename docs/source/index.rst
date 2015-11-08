.. Fedora Release Engineering documentation master file, created by
   sphinx-quickstart on Tue Oct 20 14:43:54 2015.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

==========================
Fedora Release Engineering
==========================

Contents:

.. toctree::
    :maxdepth: 3

    overview
    philosophy
    sop

This page contains information about the Fedora Release Engineering team.

.. _releng-contact-info:

Contact Information
===================
* IRC: ``#fedora-releng`` on irc.freenode.net
* Mailing List: `rel-eng@lists.fedoraproject.org <https://admin.fedoraproject.org/mailman/listinfo/rel-eng>`_
* Issue tracker: `Fedora Rel-Eng Trac Tickets <https://fedorahosted.org/rel-eng/newticket>`_

If you want the to get something done (e.g. moving packages to buildroots or
into frozen compositions) by the ReleaseEngineering Team, please create a
ticket in the issue tracker mentioned above. Please enter your FAS-username or
e-mail address in the respective textbox, to make sure the team can contact
you.

.. _index-team-composition:

Team Composition
================

* `Dennis Gilmore (dgilmore) <https://fedoraproject.org/wiki/User:Ausil>`_ (Lead)
* `Kevin Fenzi (nirik) <https://fedoraproject.org/wiki/User:kevin>`_
* `Till Maas (tyll) <https://fedoraproject.org/wiki/User:till>`_
* `Jon Disnard (masta) <https://fedoraproject.org/wiki/User:parasense>`_
* `Dan Horák (sharkcz) <https://fedoraproject.org/wiki/User:sharkcz>`_ (secondary arches)
* `Peter Robinson (pbrobinson) <https://fedoraproject.org/wiki/User:pbrobinson>`_
* `Pavol Babincak (pbabinca) <https://fedoraproject.org/wiki/User:pbabinca>`_
* `Adam Miller (maxamillion) <https://fedoraproject.org/wiki/User:maxamillion>`_

Release Team members are approved by FESCo.  However, FESCo has
delegated this power to the Release Team itself.  If you want to join
the team, please read :ref:`join-releng`.

What is Fedora Release Engineering?
===================================

For a Broad Overview, see :doc:`overview <overview>`.

Why we do things the way we do them
===================================

For information on the Fedora Release Engineering Philosophy, see
:doc:`philosophy <philosophy>`.

Fedora Release Engineering Leadership
=====================================

Dennis Gilmore (dgilmore on IRC, FAS username ausil)

Leadership is currently appointed by FESCo with input from the current release
team.

Things we Do
============

* Create official Fedora releases.
    * Fedora Products
        * Cloud
        * Server
        * Workstation
    * Fedora Spins
* Report progress towards release from `branched`_ creation on.
* Give reports to FESCo on changes to processes.
* If something is known to be controversial, we let FESCo know before
  implementing otherwise implementation generally happens concurrently to
  reporting.
* Set policy on freeze management
* Administrate the build system(s)
* Remove unmaintained packages from Fedora
* Push updated packages
* write and maintain tools to compose and push Fedora


.. _join-releng:

Joining Release Engineering
===========================

Much of rel-eng's communication is via IRC. One of the best ways to initially
get involved is to attend one of the meetings and say that you're interested
in doing some work during the open floor at the end of the meeting.  If you
can't make the meeting times, you can also ping one of us on IRC or sign up for
the `mailing list <https://admin.fedoraproject.org/mailman/listinfo/rel-eng>`_.

Since release engineering needs special access to systems essential to Fedora
people new to rel-eng will usually get access a little bit at a time.
Typically people won't immediately be granted the ability to sign packages and
push updates for example. A couple of tasks you could start out with are
troubleshooting why builds are failing (and if rel-eng could take actions to
fix it) as the requests are submitted to trac or help with scripts for various
rel-eng tasks.

There are also a number of tools that Fedora Release Engineering uses and
relies upon, working on improving these upstream to fascilitate with new
things that the Fedora Project is aiming to deliver is also a great way to get
involved with Fedora Rel-Eng.

How we do it
============

See our :doc:`Standard Operating Procedures <sop>` for details on how we do
the things we do.

Most discussions regarding release engineering will happen either in
`#fedora-releng` or on the releng mailing list. For requests, please consult
the :ref:`releng-contact-info`

Meetings
========
rel-eng holds regular meetings every Monday at 14:30 UTC in `#fedora-meeting-1`
on the Freenode IRC network.

* `Meeting agendas <https://fedorahosted.org/rel-eng/report/10>`_ are created
  from open tickets in Trac that contain the meeting keyword.

Meeting Minutes
---------------
Minutes are posted to the rel-eng mailing list. They are also available at the
`Meetbot team page for releng
<https://meetbot.fedoraproject.org/sresults/?group_id=releng&type=team>`_

There are also `historical Meeting Minutes for 2007-04-16 to 2009-05-04
<https://fedoraproject.org/wiki/ReleaseEngineering/Meetings>`_.

Current activities
==================

See our `kanban board`_ for ongoing project work.

See our `ticket queue <https://fedorahosted.org/rel-eng/report>`_ for the
things we are currently working.

See `Releases <https://fedoraproject.org/wiki/Releases>`_ for information
about Fedora releases, including schedules.

Freeze Policies
===============

* `Milestone (Alpha, Beta, Final) freezes <https://fedoraproject.org/wiki/Milestone_freezes>`_
* `String Freeze Policy`_ (Same time as Alpha Freeze)
* `Change freeze policy <https://fedoraproject.org/wiki/Changes/Policy>`_
  (that's 'Change' as in 'feature')
* `Updates Policy <https://fedoraproject.org/wiki/Updates_Policy>`_
  (not technically a freeze, but of interest)

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

.. _branched: https://fedoraproject.org/wiki/Releases/Branched
.. _kanban board:
    http://taiga.cloud.fedoraproject.org/project/acarter-fedora-docker-atomic-tooling/kanban
.. _String Freeze Policy:
    https://fedoraproject.org/wiki/Software_String_Freeze_Policy
