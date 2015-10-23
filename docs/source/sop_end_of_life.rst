===========
End Of Life
===========

Description
===========
Each release of Fedora is maintained as laid out in the `maintenance
schedule`_. At the conclusion of the maintenance period, a Fedora release
enters ``end of life`` status. This procedure describes the tasks necessary to
move a release to that status.

Actions
=======

Set date
--------
* Releng responsibilities:
    * Follow guidelines of `maintenance schedule`_
    * Take into account any infrastructure or other supporting project resource
      contention
    * Announce the closure of the release to the package maintainers.

Reminder announcement
---------------------
* from rel-eng to f-devel-announce, f-announce-l, including
    * date of last update push (if needed)
    * date of actual EOL

Koji tasks
----------
* disable builds by removing targets

  ::

    koji remove-target f19
    koji remove-target f19-updates-candidate

* Purge from disk the signed copies of rpms that are signed with the EOL'd
  release key

Bodhi tasks
-----------
* In puppet, set the push scripts to not push the old release:

  ::

    diff --git a/configs/system/fedora-updates-push
    b/configs/system/fedora-updates-push
    index 2c05334..39e25f7 100755
    --- a/configs/system/fedora-updates-push
    +++ b/configs/system/fedora-updates-push
    @@ -3,7 +3,7 @@
     SOURCE=/mnt/koji/mash/updates
     DEST=/pub/fedora/linux/updates/

    -for rel in 11 12 13; do
    +for rel in 12 13; do

     rsync -rlptDvHh --delay-updates $RSYNC_OPTS --exclude "repodata/*" \
             $SOURCE/f$rel-updates/ $DEST/$rel/ &>/dev/null
    @@ -11,7 +11,7 @@ rsync -rlptDvHh --delay-updates $RSYNC_OPTS --delete
    --delete-after \
             $SOURCE/f$rel-updates/ $DEST/$rel/ &>/dev/null

     done
    -for rel in 11 12 13; do
    +for rel in 12 13; do

     rsync -rlptDvHh --delay-updates $RSYNC_OPTS --exclude "repodata/*" \
             $SOURCE/f$rel-updates-testing/ $DEST/testing/$rel/ &>/dev/null

* Take a bodhi database snapshot for good measure

  ::

    [masher@releng04 bodhi]$ bodhi-pickledb save

* Remove all updates and comments associated with the release

  ::

    [masher@releng04 bodhi]$ bodhi-rmrelease F19

PackageDB
---------

Set the release to be End of Life in the PackageDB. A admin can login and do
this from the web interface.

Source Control (git)
--------------------

* Branches for new packages in git are not allowed for distribution X after
  the Fedora X+2 release. New builds are no longer allowed for EOL Fedora
  releases.

Fedora Program Manager Tasks
----------------------------

* Close all open bugs
* `End of Life Process`_

Bugzilla
--------

* Update the description of Fedora in bugzilla for the current releases.
    * Get someone from sysadmin-main to login as the
      fedora-admin-xmlrpc@redhat.com user to bugzilla.
    * Have them edit the description of the Fedora product here:
      https://bugzilla.redhat.com/editproducts.cgi?action=edit&product=Fedora

Docs tasks
----------

* any?

Badges tasks
------------

* Update the `cold undead hands`_ badge.

Cloud tasks
-----------

.. note::
    FIXME: This needs updating, I'm pretty sure we need to do something with
    fedimg here

* Remove unsupported EC2 images from
  https://fedoraproject.org/wiki/Cloud_images#Currently_supported_EC2_images

Taskotron tasks
---------------

`File Taskotron ticket`_ and ask for the EOL'd release support to be removed.
(Log in to Phabricator using your FAS_account@fedoraproject.org email address).

Final announcement
------------------

* from releng to f-announce-l
    * on EOL date if at all possible
    * link to previous reminder announcement (use HTTPS)

Announcement content
^^^^^^^^^^^^^^^^^^^^

.. note::
    FIXME: This needs updating, that URL is a dead link

* Consider this [http://www.openoffice.org/servlets/ReadMsg?list=announce&msgNo=407
  EOL announcement] from openoffice.org

    * Note FAQ

Update eol wiki page
^^^^^^^^^^^^^^^^^^^^

https://fedoraproject.org/wiki/End_of_life update with release and number of
days.

Verification
============

.. note::
    FIXME: This section needs some love

Consider Before Running
=======================
* Resource contention in infrastructure, such as outages
* Extenuating circumstances for specific planned updates, if any
* ot

.. _maintenance schedule:
    https://fedoraproject.org/wiki/Fedora_Release_Life_Cycle#Maintenance_Schedule
.. _End of Life Process:
    https://fedoraproject.org/wiki/BugZappers/HouseKeeping#End_of_Life_.28EOL.29
.. _cold undead hands:
    https://git.fedorahosted.org/cgit/badges.git/tree/rules/you-can-pry-it-from-my-cold-undead-hands.yml
.. _File Taskotron ticket:
    https://phab.qadevel.cloud.fedoraproject.org/maniphest/task/create/?projects=PHID-PROJ-prgpoumlmfdczdr4dyv3 
