===============================
Stage Final Release for Mirrors
===============================


Description
===========
When the release has been fully tested and approved at the "Go/No-Go" meeting
it is ready for release to the Fedora mirrors.

Action
======
#. Sign all ``CHECKSUM`` files:

   ::

        $ for checksum in $(find /mnt/fedora_koji/compose/23_Alpha_RC2/23_Alpha/ -name  *CHECKSUM);
        do
            cat $checksum >/tmp/sum && \
                sigul sign-text -o /tmp/signed fedora-23 /tmp/sum && \
                chmod 644 /tmp/signed && \
                sg releng "mv /tmp/signed $checksum";
        done

#. Prepare the master mirror by logging into releng2:

   ::
        $ ssh <fas-username>@gateway.fedoraproject.org
        $ ssh releng2

   ::

        $ sudo -u ftpsync mkdir -p /pub/fedora/linux/releases/13/{Fedora,Everything,Live}
        $ sudo -u ftpsync chmod 700 /pub/fedora/linux/releases/13/

#. Synchronize the ``Everything`` tree with the mirrors from releng2:

   ::
        $ sudo -u ftpsync rsync -rlptDHhv --progress --stats --exclude images/ - \
            --exclude EFI --exclude isolinux --exclude .treeinfo \
            --exclude .discinfo - --link-dest=/pub/fedora/linux/development/13/ \
            /mnt/koji/mash/branched-20100518/13/ \
            /pub/fedora/linux/releases/13/Everything/

#. Synchronize the ``Fedora`` tree with the mirrors from releng2:

   ::

        $ sudo -u ftpsync rsync -rlptDHhv --progress --stats - \
            --link-dest=/pub/fedora/linux/development/13/ \
            jkeating@compose-x86-01:/srv/pungi/13.RC4/Fedora/ \ 
            /pub/fedora/linux/releases/13/Fedora/

#. Synchronize the Live images with the mirrors from releng2:

   ::

        $ sudo -u ftpsync rsync -rlptDHhv --progress --stats --exclude \*.log \
            jkeating@compose-x86-01:/srv/pungi/live/Fedora-13-i686-Live{,-KDE}/ \
            /pub/fedora/linux/releases/13/Live/i686/

#. Change file permissionsOpen for mirrors (also known as the *mirror stage
   bit flip*) on releng2:

   ::

        $ sudo -u ftpsync chmod 750 /pub/fedora/linux/releases/13

Verification
============
Verification is somewhat difficult as one cannot look at the content via the
web server due to permissions.  Typically we ask somebody from the
Infrastructure team to give the tree a second set of eyes.

Consider Before Running
=======================
Hope the release is good!

