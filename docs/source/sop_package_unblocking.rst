==================
Package Unblocking
==================

Description
===========
Packages are sometimes unblocked from Fedora, usually when a package had been
orphaned and now has a new owner.  When this happens, release engineering
needs to "unblock" the package from koji tags.

Action
======

Find Unblock requests
---------------------

Unblock requests are usually reported in the rel-eng trac instance at
Fedorahosted in the component koji. You can use a trac query to list all
`unassigned Koji tickets`_. This query also includes requests, that are not an
unblock request, because there is no automated way to distinguish them. The
results of the query are also available as an RSS feed, the link is in the
footer of the page.

Perform the unblocking
----------------------

First assign the ticket to yourself to show, that you are handling the request.

Discover proper place to unblock
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The ticket should tell you which Fedora releases to unblock the package in.
Typically it'll say "Fedora 13" or "F14".  This means we need to unblock it at
that Fedora level and all future tags.  However depending on where the package
was blocked we may have to do our unblock action at a different Fedora level.

To discover where a package is blocked, use the ``list-pkgs`` method of koji.

::

    $ koji list-pkgs --help
    Usage: koji list-pkgs [options]
    (Specify the --help global option for a list of other help options)

    Options:
      -h, --help         show this help message and exit
      --owner=OWNER      Specify owner
      --tag=TAG          Specify tag
      --package=PACKAGE  Specify package
      --quiet            Do not print header information
      --noinherit        Don't follow inheritance
      --show-blocked     Show blocked packages
      --show-dups        Show superseded owners
      --event=EVENT#     query at event
      --ts=TIMESTAMP     query at timestamp
      --repo=REPO#       query at event for a repo

For example if we wanted to see where python-psco was blocked we would do:

::

    $ koji list-pkgs --package python-psyco --show-blocked
    Package                 Tag                     Extra Arches     Owner          
    ----------------------- ----------------------- ---------------- ---------------
    python-psyco            dist-f14                                 konradm         [BLOCKED]
    python-psyco            olpc2-ship2                              shahms         
    python-psyco            olpc2-trial3                             shahms      
    ...

Here we can see that it was blocked at dist-f14.  If we got a request that was
to unblock it before f14, we can simply use the dist-f14 target to unblock.
However if they want it unblocked after f14, we would use the earliest
dist-f?? tag the user wants, such as  dist-f15 if the user asked for it to be
unblocked in Fedora 15+

Performing the unblock
^^^^^^^^^^^^^^^^^^^^^^

To unblock a package for a tag, use the ``unblock-pkg`` method of Koji.

::

    $ koji unblock-pkg --help
    Usage: koji unblock-pkg [options] tag package [package2 ...]
    (Specify the --help global option for a list of other help options)

    Options:
      -h, --help  show this help message and exit

For example, if we were asked to unblock python-psyco in F14 we would issue:

::

    $ koji unblock-pkg dist-f14 python-psyco

Now the ticket can be closed.

Verification
============
To verify that the package was successfully unblocked use the ``list-pkgs``
koji command:

::

    $ koji list-pkgs --package python-psyco --show-blocked

We should see the package listed as not blocked at dist-f14 or above:


::

    Package                 Tag                     Extra Arches     Owner          
    ----------------------- ----------------------- ---------------- ---------------
    python-psyco            olpc2-trial3                             jkeating       
    python-psyco                   olpc2-ship2                              jkeating       
    python-psyco                   olpc2-update1                            jkeating       
    python-psyco                   trashcan                                 jkeating       
    python-psyco                   f8-final                                 jkeating       
    ...

We should not see it listed as blocked in dist-f14 or any later Fedora tags.

Consider Before Running
=======================
* Watch the next day's rawhide/branched/whatever report for a slew of broken
  deps related to the package.  We may have to re-block the package in order
  to fix the deps.

.. _unassigned Koji tickets:
    https://fedorahosted.org/rel-eng/query?status=new&status=assigned&status=reopened&component=koji&owner=rel-eng%40lists.fedoraproject.org&order=priority
