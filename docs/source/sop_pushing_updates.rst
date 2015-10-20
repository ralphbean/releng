===============
Pushing Updates
===============

Description
===========

Fedora updates are typically pushed once a day. This SOP covers the steps
involved.

Coordinate
----------

Releng has a rotation of who pushes updates when. Please coordinate and only
push updates when you are expected to or have notified other releng folks you
are doing so. See: https://apps.fedoraproject.org/calendar/release-engineering/
for the list or on irc you can run ``.pushduty`` in any channel with zodbot to
see who is on duty this week.

Login to machine to sign updates
--------------------------------

Login to a machine that is configured for sigul client support and has the
bodhi client installed. Currently, this machine is:
``bodhi-backend01.phx2.fedoraproject.org``

Decide what releases you're going to push.
------------------------------------------

* If there is a Freeze ongoing, you SHOULD NOT push all stable requests for a
  branched release, only specific blocker or freeze exception requests that QA
  will request in a releng ticket.

* If there is no Freeze ongoing you can push all Fedora and EPEL releases at
  the same time if you wish. 

* From time to time there may be urgent requests in some branches, you can only
  push those if requested. Note however that bodhi2 will automatically push
  branches with security updates before others.

Get a list of packages to push
------------------------------

::

    $ cd /var/cache/sigul
    $ sudo -u masher bodhi-push --releases '23 22 21 5 6 7' --username <yourusername>
    <enter your password+2factorauth, then your fas password>

You can say 'n' to the push at this point if you wish to sign packages (see
below). Or you can keep this request open in a window while you sign the
packages, then come back and say y.

List the releases above you wish to push from: 23 22 21 5 6 7, etc

You can also specify ``--request=testing`` to limit pushes. Valid types are
``testing`` or ``stable``.

The list of updates should be in the cache directory named ``Stable-$Branch``
or ``Testing-$Branch`` for each of the Branches you wished to push.

During freezes you will need to do two steps: (If say, fedora 23 branched was
frozen):

::

    $ cd /var/cache/sigul
    $ sudo -u masher bodhi-push --releases 23 --request=testing \
        --username <username>

Then

::

    $ cd /var/cache/sigul
    $ sudo -u masher bodhi-push --releases '22 21 5 6 7' --username <username>

Sign the packages.
------------------

* Sign builds using scripts/sigulsign_unsigned.py from releng git repo

  ::

    $ ./sigulsign_unsigned.py -vv --write-all \
        --sigul-batch-size=25 fedora-22 \
        $(cat /var/cache/sigul/Stable-F22 /var/cache/sigul/Testing-F22)

(Make sure you sign each release with the right key... ie, 'fedora-19' key
with F19 packages, or 'epel-5' with EL-5 packages)

Here is another example, inside a loop:

::

    for i in 23 22 21;
    do
        NSS_HASH_ALG_SUPPORT=+MD5 ~/releng/scripts/sigulsign_unsigned.py \
            fedora-$i -v --write-all \
            --sigul-batch-size=25 $(cat /var/cache/sigul/{Stable,Testing}-F${i});
    done

    for i in  7  6  5;
    do
        NSS_HASH_ALG_SUPPORT=+MD5 ~/releng/scripts/sigulsign_unsigned.py \
            epel-$i   -v --write-all \
            --sigul-batch-size=25 $(cat /var/cache/sigul/{Stable,Testing}-*EL-${i});
    done

* You may need to add ``NSS_HASH_ALG_SUPPORT=+MD5`` before
  ``sigulsign_unsigned`` (or add it to your ~/.bashrc).

* If signing process struggles to finish, then consider adjusting the
  ``--sigul-batch-size=N`` to ``1``, which is more resilient but much slower.

Repeat gathering updates and signing steps
------------------------------------------

After gathering the list of updates and signing them, repeat the process until
there are no new updates to be signed. You want to do this because as you are
signing updates, maintainers are submitting new ones. There is a window while
you are signing that a new update will be added and if you just push then, the
push will fail with an unsigned package.

Perform the bodhi push
----------------------

Re-run the earlier bodhi command from step 2 and say 'y' to push.

Verification
============
#. Monitor the sysemd journal

   ::

    $ sudo journalctl -o short -u fedmsg-hub -l -f

#. Watch for fedmsgs through the process. It will indicate what releases it's
   working on, etc. You may want to watch in ``#fedora-fedmsg``.

   ::

        bodhi.masher.start -- kevin requested a mash of 48 updates
        bodhi.mashtask.start -- bodhi masher started a push
        bodhi.mashtask.mashing -- bodhi masher started mashing f23-updates
        bodhi.mashtask.mashing -- bodhi masher started mashing f22-updates-testing
        ...
        bodhi.update.complete.stable -- moceap's wondershaper-1.2.1-5.fc23 bodhi update completed push to stable https://admin.fedoraproject.org/updates/FEDORA-2015-13052
        ...
        bodhi.errata.publish -- Fedora 23 Update: wondershaper-1.2.1-5.fc23 https://admin.fedoraproject.org/updates/FEDORA-2015-13052
        bodhi.mashtask.complete -- bodhi masher successfully mashed f23-updates
        bodhi.mashtask.sync.wait -- bodhi masher is waiting for f22-updates-testing to hit the master mirror

#. Seach for problems with a particular push: 

   ::

        sudo journalctl --since=yesterday -o short -u fedmsg-hub | grep dist-6E-epel (or f22-updates, etc)

4. Note: Bodhi will look at the things you have told it to push and see if any have security updates, those branches will be started first. It will then fire off threads (up to 3 at a time) and do the rest.

Consider Before Running
=======================
Pushes often fall over due to tagging issues or unsigned packages.  Be
prepared to work through the failures and restart pushes from time to
time

::

    $ sudo -u masher bodhi-push --resume

Bodhi will ask you which push(es) you want to resume.

Consider testing if the mash lock file exists.
May indicate a previous push has not completed, or somehow failed:

::

    $ ls /mnt/koji/mash/updates/MASHING-*

Common issues / problems with pushes
====================================

* When the push fails due to new unsigned packages that were added after you
  started the process. re-run step 4a or 4b with just the package names that
  need to be signed, then resume.

* When the push fails due to an old package that has no signature, run:
  ``koji write-signed-rpm <gpgkeyid> <n-v-r>`` and resume.

* When the push fails due to a package not being tagged with updates-testing
  when being moved stable: ``koji tag-pkg dist-<tag>-updates-testing <n-v-r>``

* When signing fails, you may need to ask that the sigul bridge or server be
  restarted.

* If the updates push fails with a: 
  ``OSError: [Errno 16] Device or resource busy: '/var/lib/mock/*-x86_64/root/var/tmp/rpm-ostree.*'``
  You need to umount any tmpfs mounts still open on the backend and resume the push.

* If the updates push fails with:
  ``"OSError: [Errno 39] Directory not empty: '/mnt/koji/mash/updates/*/../*.repocache/repodata/'``
  you need to restart fedmsg-hub on the backend and resume.

Other issues should be addressed by releng or bodhi developers in
``#fedora-releng``.


