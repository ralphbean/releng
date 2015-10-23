========================
Remove dist-git branches
========================

Description
===========
Release Engineering is often asked by maintainers to remove branches in dist-git
by maintainers.

Action
======
#. Log into pkgs.fedoraproject.org

   ::

        ssh <fas-username>@pkgs.fedoraproject.org

#. Change to the package's directory

   ::

        cd /srv/git/rpms/<package>.git/

#. Remove the branch

   ::

        git branch -D <branchname> </pre>

erification
===========
To verify just list the branches.

::

    git branch

Consider Before Running
=======================
Make sure that the branch in question isn't one of our pre-created branches
``f??/master``, ``olpc?/master``, ``el?/master``
