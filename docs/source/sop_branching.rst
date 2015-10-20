=========
Branching
=========

Description
===========
This SOP covers how to make git and pkgdb branches for packages, either for
new packages that have passed review, or for existing packages that need a new
branch (e.g. EPEL). Release Engineering has written a script to automate this
process.

Normal Action (automated)
=========================

#. On your local system (not on an infrastructure hosted system), be sure you
   have the following packages installed:

   * python-bugzilla
   * python-configobj
   * python-fedora

#. Run "bugzilla login" and successfully receive an Authorization cookie.

#. Clone the fedora-infrastructure tools repository:
    ::

        git clone ssh://git.fedorahosted.org/git/releng.git

#. In scripts/process-git-requests, run "process-git-requests". Answer the
   prompts.

Manual Action
=============

Creating a new branch for an existing package
---------------------------------------------

#. ssh into ``pkgs.fedoraproject.org``

#. ``pkgdb-client edit -u $YOURUSERNAME -b $NEWBRANCH --master=devel $NAMEOFPACKAGE``

#. ``pkgdb2branch.py $NAMEOFPACKAGE``
