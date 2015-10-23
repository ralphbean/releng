========================
Composing Testing Images
========================

Description
===========
From time to time the Quality Assurance team requests official images for
testing (boot images only, no full media).  Release Engineering is
responsible for creating them.

Action
======
Fulfilling the images for testing ticket requires composing the images,
uploading the images, and updating the ticket.

Composing the images
--------------------
#. Log into compose system: ``compose-x86-01``

   ::

        $ ssh gateway.fedoraproject.org
        $ ssh compose-x86-01

#. Update the compose kickstart file in in the git repo in
   ``/srv/pungi/spin-kickstarts/``

   ::

        $ cd /srv/pungi/spin-kickstarts/
        $ git pull

#. Update / create chroots (fedora-devel-compose-{i386,x86_64})

   ::

        $ mock -r fedora-devel-compose-i386 --shell
        $ yum update

   If the chroot does not exist yet you will have to create it:

   ::

        $ mock -r fedora-devel-compose-i386 --init

#. Shell into the chroot (this is not necessary if you already shelled into
   update above)

   ::

        $ mock -r fedora-devel-compose-i386 --shell

#. Run pungi to create the images:

   ::

        $ pungi -c /srv/pungi/spin-kickstarts/fedora-install-fedora.ks \
            --destdir /srv/pungi/rawhide-20100122.0 \
            --cachedir /srv/pungi/cache \
            --nosource \
            --nodebug --ver development -GCB

   When done, exit the mock chroot.

Upload the images
-----------------
We host the images on alt.fedoraproject.org which has an internal name of
``secondary1``.

#. Create the output dir on ``secondary1``

   ::

        $ ssh secondary1 mkdir -p /srv/pub/alt/stage/rawhide-20100122

#. rsync the output, minus the packages and repodata, to
   ``alt.fedoraproject.org``

   ::

        $ rsync -avHh --progress --stats --exclude Packages \
               --exclude repodata --exclude repoview \
               /srv/pungi/rawhide-20100122.0/development/ \
               secondary1:/srv/pub/alt/stage/rawhide-20100122/

#. Update the 'to be tested' symlink:

   ::

        $ ssh secondary1 ln -sfT rawhide-20100122 /srv/pub/alt/stage/rawhide-testing

Update the ticket
-----------------
The ticket should be closed when the images are uploaded and the symlink has
been adjusted.  The full path should be noted for clarity sake.

If there are delays in the compose, the ticket should be updated with that
information and (if known) amount of delay in finishing the compose.

Verification
============
Verification can be done as the task steps are being performed.

Image Creation
--------------
When pungi exits, you can verify that the ``development/<arch>/os/images/``
directory exists and has content.  That path is relative to the destination
directory you provide pungi.

Upload the images
-----------------
One can simply browse to
http://dl.fedoraproject.org/pub/alt/stage/rawhide-testing and check the dates
on the directories.

Updating the Ticket
-------------------
One can click the link provided in the ticket update and ensure the path is
correct.  Verifying that the ticket is closed should be pretty self evident.

Consider Before Running
=======================
Many things can hinder a compose, broken deps in the chroot set, broken deps
in the compose set, bugs in the compose software, etc...  If any problem is
ran into along the way, it is best to alert QA via a ticket update, and then
work with the appropriate party to clear the obstruction.

Some of these tasks take a long time to finish, so it is highly recommended
that you run these tasks in a ``screen`` or ``tmux`` session.

If you need to make use of freshly built packages since the last rawhide
compose, you can create a local repository.  ``/srv/pungi/bleed/<arch>/`` on
the compose system can be used as a temporary repo for new packages.  Don'
forget to update the mock chroot with the new packages (if appropriate) and to
add the temporary repo to the ``spin-kickstarts/fedora-install-fedora.ks``
file for use by pungi.

Disk space on ``secondary1`` is limited, so if you need to go through a number
of composes before you get one that tests well, be sure to prune the failed
composes.  This is true of disk space on the compose host too, be sure to trim
``/srv/pungi/`` of composes that are no longer needed locally.
