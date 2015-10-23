======================
Adding Side Build Tags
======================

Description
===========
Bigger Features can take a while to stabilise and land or need a large number
of packages to be built against each other, this is easiest served by having a
separate build tag for the development work.  This SOP will describe the steps
necessary to prepare the new build target.

Action
======
Adding a side build target is fairly straightforward,  but comes with a cost
of extra newRepo tasks in koji.

Koji
----
In koji a tag needs to be made,  it needs to inherit from the ``-build`` tag of
the base your wanting to develop against,  this is to ensure that group info
makes it into your tag so you can build successfully.  As we will be building
against this tag we need to give it the needed arches also.

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

    $ koji add-target --help
    Usage: koji add-target name build-tag <dest-tag>
    (Specify the --help global option for a list of other help options)

    Options:
    -h, --help  show this help message and exit

For example if we wanted to create the EPEL tags to build XFCE , we would do
the following:

::

    koji add-tag epel6-xfce48 --parent=dist-6E-epel-build --arches="i686,x86_64,ppc64"
    koji add-target epel6-xfce48 epel6-xfce48 

A Fedora example would be:

::
    koji add-tag f23-gnutls --parent=f23-build --arches="armv7hl,i686,x86_64"
    koji add-target f23-gnutls f23-gnutls 

Verification
============
Check in koji that a newRepo task is created for your new tag and has the
appropriate arches

Cleanup
=======
When the builds are completed to remove the target and merge builds across

::

    koji remove-target epel6-xfce48

to merge builds across edit mass-tag.py in the releng git repo and run it.

Tags are ``never`` removed.

Consider Before Running
=======================

* Is the amount of work to be done worth the cost of newRepo tasks.
* If there is only a small number of packages  overrides may be better.
* Is there a mass-rebuild going on? no side tags are allowed while a mass
  rebuild is underway

