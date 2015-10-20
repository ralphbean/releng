================================
Creating Live Translation Images
================================

Description
===========
Translators ask for an image to verify all builds with translations are done.
This image can just be a hardlink to the latest nightly desktop live images,
since the translators can update those to updates-testing and newer builds.

Action
======
#. Log into secondary1.fedoraproject.org:

   ::

        $ cd /srv/pub/alt/stage/
        $ mkdir f??-translation/
        $ cp -al ../../nightly-composes/desktop/* .

#. Update the release engineering ticket with the url:

   ::

        http://alt.fedoraproject.org/pub/alt/stage/f??-translation
        http://serverbeach1.fedoraproject.org/pub/alt/stage/f-??-translation

Verification
============
* Verify by clicking the url and making sure the files show up

Consider Before Running
=======================
* Make sure image can actually boot
* Make sure using image composed after deadline

