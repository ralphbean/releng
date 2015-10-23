===============================
Update Branched Last Known Good
===============================


Description
===========

.. note::
    FIXME - There was no description in the wiki

Action
======
#. Respond to the ticket and take ownership.

#. Rsync images from the tree QA claims is LNG to alt. Do this from a system
   that mounts /mnt/koji such as releng1.  EG syncing the images from 20100315
   as LNG:

   ::

        $ rsync -avHh --progress --stats --exclude Packages  \
             --exclude repodata --exclude repoview --exclude debug \
             --exclude drpms --exclude source \
             /mnt/koji/mash/branched-20100315/13/ \
             secondary1:/srv/pub/alt/stage/branched-20100315/

#. Update the lng symlink

   ::
        $ ssh secondary1 ln -sfT branched-20100315 /srv/pub/alt/stage/branched-lng

#. Update the ticket when complete and close it.

Verification
============

.. note::
    FIXME - There was no verification section in the wiki

Consider Before Running
=======================

.. note::
    FIXME - There was no consider before running section in the wiki
