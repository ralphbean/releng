=======================
Package Announce Update
=======================

Description
===========
Must add a new topic filter for the newly pending release about to get updates.

Action
======
#. Visit https://admin.fedoraproject.org/mailman/admin/package-announce and log
   in
#. Click on topics
#. Add a new topic before the Security topic:

   ::

        Topic Name: Fedora 13
        Regexp: Fedora\ 13
        Description: Updates and announcements for Fedora 13

#. Submit

Verification
============
* Verify requires somebody subscribed and using topic filters to confirm
  correct filtering once mails start to go out.

Consider Before Running
=======================

.. note::
    FIXME This needs some love
