===============
Update Critpath
===============

.. note::
    Critpath = "Critical Path"

    This is a collection of packages deemed "critical" to Fedora

Description
===========

Packagedb has information about which packages are critpath and which are not.
A script that reads the yum repodata (critpath group in comps, and the package
dependencies) is used to generate this.  Since package dependencies change,
this list should be updated periodically.

Action
======

#. Checkout the releng git repo:

   ::

        git clone git://git.fedorahosted.org/git/releng

#. Check the script to see if the list of releases needs to be updated:

   ::

        for r in ['12', '13', '14', '15', '16', '17']: # 13, 14, ...
            releasepath[r] = 'releases/%s/Everything/$basearch/os/' % r
            updatepath[r] = 'updates/%s/$basearch/' % r

        # Branched Fedora goes here
        branched = '18'

   The for loop has the version numbers for releases that have gone past final.
   branched has the release that's been branched from rawhide but not yet hit
   final.  (These have different paths in the repository and may not have an
   updates directory, thus they're in separate sections).

#. Run the script with the release to generate info for (for a release that's
   hit final, this is the release number example: "17".  For branched, it's
   "branched"):

   ::
        ./critpath.py --srpm -o critpath.txt branched

#. Run the update script to add that to the pkgdb:

   ::

        ./update-critpath --user toshio f18 critpath.txt

   The username is your fas username.  You must be in cvsadmin to be able to
   change this.  The release is given in pkgdb format (f17, f18, devel, etc).
   critpath.txt is the file that the output of critpath.py went into.  The
   script will prompt for your FAS password to verify your identity with the
   pkgdb.
