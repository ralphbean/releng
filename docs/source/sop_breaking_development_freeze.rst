===========================
Breaking Development Freeze
===========================

``FIXME: NEED TO FIGURE OUT HOW TO FEDORA-VERSION-NEXT``

Description
===========
Packages which require an exception to freeze policies must be run through
this SOP.

The following freeze policies are set for the following significant release
milestones:

* `Alpha Freeze`_
* `String Freeze`_
* `Beta Freeze`_
* `Final Freeze`_

See `Fedora Release Life Cycle`_ for a summary of all the freezes, dates, and
exception handling, or the release engineering [https://fedorapeople.org/groups/schedule/f-{{FedoraVersionNumber|next}}/f-{{FedoraVersionNumber|next}}-releng-tasks.html calendar for the current release].

Action
======
The commands to tag a package properly once it has been accepted:

::

    $ koji move-pkg --force dist-f{{FedoraVersionNumber|next}}-updates-candidate dist-f{{FedoraVersionNumber|next}} <PKGNAME>
    $ koji tag-pkg --force f{{FedoraVersionNumber|next}}-<RELEASE> <PKGNAME>

Where <PKGNAME> is the package name, and <RELEASE> is the first release in which the package should land (e.g. alpha, beta, final).  

Verification
============
The ``koji`` client reports success or failure. For secondary verification,
run these commands:

::

    $ koji latest-pkg dist-f{{FedoraVersionNumber|next}} <PKGNAME>
    $ koji latest-pkg dist-f{{FedoraVersionNumber|next}}-updates-candidate <PKGNAME>

Consider Before Running
=======================
* Change agrees with stated policies (see links above)
* Approval for change has been granted under `Blocker Bug Process`_ or
  `Freeze Exception Bug Process`


.. _Alpha Freeze: https://fedoraproject.org/wiki/Milestone_freezes
.. _Beta Freeze: https://fedoraproject.org/wiki/Milestone_freezes
.. _Final Freeze: https://fedoraproject.org/wiki/Milestone_freezes
.. _String Freeze: https://fedoraproject.org/wiki/Software_String_Freeze_Policy
.. _Fedora Release Life Cycle:
    https://fedoraproject.org/wiki/Fedora_Release_Life_Cycle
.. _Blocker Bug Process:
    https://fedoraproject.org/wiki/QA:SOP_blocker_bug_process
.. _Freeze Exception Bug Process:
    https://fedoraproject.org/wiki/QA:SOP_freeze_exception_bug_process
