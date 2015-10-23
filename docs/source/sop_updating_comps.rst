==============
Updating Comps
==============

Description
===========
When we start a new Fedora development cycle (when we branch rawhide) we have
to create a new comps file for the new release.  This SOP covers that action.

Action
======

#. clone the comps repo

   ::

        $ git clone ssh://git.fedorahosted.org/git/comps

#. Create the new comps file for next release:

   ::

        $ cp comps-f14.xml.in comps-f15.xml.in

#. Edit Makefile to update comps-rawhide target

   ::

        - -comps-rawhide: comps-f14.xml
        - -       @mv comps-f14.xml comps-rawhide.xml
        +comps-rawhide: comps-f15.xml
        +       @mv comps-f15.xml comps-rawhide.xml

#. Add the new comps file to source control:

   ::

        $ git add comps-f15.xml.in

#. Edit the list of translated comps files in po/POTFILES.in to reflect
   currently supported releases.

   ::

        -comps-f12.xml
        +comps-f15.xml

#. Send it up:

   ::
        $ git push

Verification
============
One can review the logs for rawhide compose after this change to make sure
the right comps file was used.

Consider Before Running
=======================
Nothing yet.
