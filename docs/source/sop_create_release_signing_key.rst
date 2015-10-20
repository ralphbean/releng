==========================
Create Release Signing Key
==========================

Description
===========
At the beginning of each release under development a new package signing key
is created for it.  This key is used to prove the authenticity of packages
built by Fedora and distributed by Fedora.  This key will be used to sign
all packages for the public test and final releases.

Action
======

Sigul
-----
Sigul is the signing server which holds our keys.  In order to make use of a
new key, the key will have to be created and access to the key will have to be
granted.  The ``new-key``, ``grant-key-access``, and ``change-passphrase``
commands are used.

::

    $ sigul new-key --help
    usage: client.py new-key [options] key

    Add a key

    options:
      -h, --help            show this help message and exit
      --key-admin=USER      Initial key administrator
      --name-real=NAME_REAL
                            Real name of key subject
      --name-comment=NAME_COMMENT
                            A comment about of key subject
      --name-email=NAME_EMAIL
                            E-mail of key subject
      --expire-date=YYYY-MM-DD
                            Key expiration date

    $ sigul grant-key-access --help
    usage: client.py grant-key-access key user

    Grant key access to a user

    options:
      -h, --help  show this help message and exit

    $ sigul change-passphrase --help
    usage: client.py change-passphrase key

    Change key passphrase

    options:
      -h, --help  show this help message and exit

For example if we wanted to create the Fedora 23 signing key, we would do the
following:

#. Log into a system configured to run sigul client.
#. Create the key using a strong passphrase when prompted

   ::

        $ sigul new-key --key-admin ausil --name-real Fedora \
                --name-comment 23 \
                --name-email fedora-23-primary@fedoraproject.org fedora-23

   For EPEL

   ::

        $ sigul new-key --key-admin ausil --name-real "Fedora EPEL" \
                --name-comment 7 \
                --name-email epel@fedoraproject.org epel-7

#. Wait a while for entropy.  This can take several minutes.
#. Grant key access to Fedora Account holders who will be signing packages and
   protect it with a temporary a passphrase.  For example, ``CHANGEME``

   ::

        $ sigul grant-key-access fedora-23 kevin

#. Provide the key name and temporary passphrase to signers. If they don't
   respond, revoke access until they are ready to change their passphrase.
   Signers can change their passphrase using the ``change-passphrase`` command:

   ::

        $ sigul change-passphrase fedora-23

#. When your sigul cert expires, you will need to run: 

   ::

        certutil -d ~/.sigul -D -n sigul-client-cert

   to remove the old cert, then

   ::

        sigul_setup_client

   to add a new one.

fedora-release
--------------
The fedora-release package houses a copy of the public key information.  This
is used by rpm to verify the signature on files encountered.  Currently the
fedora-release package has a single key file named after the version of the
key and the arch the key is for.  To continue our example, the file would be
named ``RPM-GPG-KEY-fedora-13-primary`` which is the primary arch key for
Fedora 13.  To create this file, use the ``get-public-key`` command from sigul:

::

    $ sigul get-public-key fedora-13 > RPM-GPG-KEY-fedora-13-primary

Add this file to the repo, and remove the previous release's file.

::

    $ cvs rm RPM-GPG-KEY-fedora-12-primary
    $ cvs add RPM-GPG-KEY-fedora-13-primary

Then make a new fedora-release build for rawhide (``FIXME: this should be its own SOP``)

fedoraproject.org
-----------------
``FIXME - WE DON'T EVEN CVS ANYMORE BECAUSE IT'S NOT THE EARLY 90s``
fedoraproject.org/keys lists information about all of our keys.  We need to
let the webteam know we have created a new key so that they can add it to the
list.

We do this by sending an email to webmaster@fedoraproject.org pointing to the
viewvc
http://cvs.fedoraproject.org/viewvc/fedora-release/RPM-GPG-KEY-fedora-13-primary?revision=1.1&root=fedora&view=co
as well as including a URL to this page so that the process is not forgotten
(see section below)

This url will have to be refreshed for the right release and CVS version

Web team SOP
^^^^^^^^^^^^

::

    # from git repo root
    cd fedoraproject.org/
    curl $KEYURL > /tmp/newkey
    $EDITOR update-gpg-keys # Add key ID of recently EOL'd version to obsolete_keys
    ./update-gpg-key /tmp/newkey
    gpg static/fedora.gpg # used to verify the new keyring
    # it should look something like this:
    # pub  4096R/57BBCCBA 2009-07-29 Fedora (12) <fedora@fedoraproject.org>
    # pub  4096R/E8E40FDE 2010-01-19 Fedora (13) <fedora@fedoraproject.org>
    # pub  4096R/97A1071F 2010-07-23 Fedora (14) <fedora@fedoraproject.org>
    # pub  1024D/217521F6 2007-03-02 Fedora EPEL <epel@fedoraproject.org>
    # sub  2048g/B6610DAF 2007-03-02 [expires: 2017-02-27]
    # it must only have the two supported versions of fedora, rawhide and EPEL
    # also verify that static/$NEWKEY.txt exists
    $EDITOR data/content/{keys,verify}.html # see git diff 1840f96~ 1840f96

sigulsign_unsigned
------------------
``sigulsign_unsigned.py`` is the script Release Engineers use to sign content in
koji.  This script has a hardcoded list of keys and aliases to the keys that
needs to be updated when we create new keys.

Add the key details to the ``KEYS`` dictionary near the top of the
``sigulsign_unsigned.py`` script.  It lives in Release Engineering's git repo
at ``ssh://git@pagure.io/releng.git`` in the ``scripts`` directory. You
will need to know the key ID to insert the correct information:

::

    $ gpg <key block from sigul get-public-key>

Public Keyservers
-----------------
We upload the key to the public key servers when we create the keys.  To do
this, we need to get the ascii key block from sigul, determine the key ID,
import they key into our local keyring, and then upload it to the key servers.

::

    $ sigul get-public-key fedora-13 > fedora-13
    $ gpg fedora-13 (The ID is the "E8E40FDE" part of 4096R/E8E40FDE)
    $ gpg --import fedora-13
    $ gpg --send-keys E8E40FDE

Mash
----
Mash is the tool that composes our nightly trees, and as such it needs to know
about the new key.  This currently is done by checking mash out from git,
editing the rawhide.mash file and sending the patch to the mash upstream.

::

    $ git clone https://git.fedorahosted.org/git/mash
    $ cd mash
    $ vim configs/rawhide.mash
    <add key to front of keys = line>
    $ git commit -m 'Add new key'
    $ git send-email --to notting@redhat.com HEAD^


``FIXME - Nottingham isn't active in Fedora RelEng lately``
Coordinate with Bill Nottingham to get a new build of mash done with the change.

Koji
----
Koji has a garbage collection utility that will find builds that meet criteria
to be removed to save space.  Part of that criteria has to do with whether or
not the build has been signed with a key.  If the collection utility doesn't
know about a key it will ignore the build.  Thus as we create new keys we need
to inform the utility of these keys or else builds can pile up.  The
configuration for the garbage collection lives within puppet.

On the puppet server in a clone edit the configs/build/koji-gc.conf file:

::

    diff --git a/configs/build/koji-gc.conf b/configs/build/koji-gc.conf
    index 8b14704..042ec35 100644
    --- a/configs/build/koji-gc.conf
    +++ b/configs/build/koji-gc.conf
    @@ -11,6 +11,7 @@ key_aliases =
         4EBFC273    fedora-10
         D22E77F2    fedora-11
         57BBCCBA    fedora-12
    +    217521F6    fedora-epel

     unprotected_keys =
         fedora-test
    @@ -21,6 +22,7 @@ unprotected_keys =
         fedora-12
         fedora-extras
         redhat-beta
    +    fedora-epel

     server = https://koji.fedoraproject.org/kojihub
     weburl = http://koji.fedoraproject.org/koji
    @@ -38,6 +40,7 @@ policy =
         sig fedora-10 && age < 12 weeks :: keep
         sig fedora-11 && age < 12 weeks :: keep
         sig fedora-12 && age < 12 weeks :: keep
    +    sig fedora-epel && age < 12 weeks :: keep

         #stuff to chuck semi-rapidly
         tag *-testing *-candidate *-override && order >= 2 :: untag

In this case the fedora-epel key was added to the list of key aliases, then
referenced in the list of unprotected_keys, and finally a policy was created
for how long to keep builds signed with this key.

Once you've made your change commit and push.  The buildsystem will pick up
this change the next time puppet refreshes.

Verification
============
We can verify that the key was created in sigul, the correct users have access
to the key, the key was added to the fedora-release package, that the website
was updated with the right key, that sigulsign_unsigned was properly updated,
and that the key was successfully updated to the public key servers.

sigul
-----
Use the ``list-keys`` command to verify that the key was indeed added to sigul:

::

    $ sigul list-keys
    Administrator's password: 
    fedora-10
    fedora-10-testing
    fedora-11
    fedora-12
    fedora-13

Our new key should be on the list.  This command expects **your**
administrative password.

Use the ``list-key-users`` command to verify all the signers have access:

::

        $ sigul list-key-users fedora-13
        Key passphrase: 
        jkeating
        jwboyer

This command expects **your** key passphrase for the key in question.

fedora-release
--------------
To verify that the key was added to this package correctly, download the latest
build from koji and run rpm2cpio on it, then run gpg on the key file:

::

    $ koji download-build --arch noarch --latest dist-f13 fedora-release
    fedora-release.noarch                                   |  39 kB     00:00 ... 

    $ rpm2cpio fedora-release-13-0.3.noarch.rpm |cpio -ivd
    ./etc/fedora-release
    ./etc/issue
    ./etc/issue.net
    ./etc/pki/rpm-gpg
    ./etc/pki/rpm-gpg/RPM-GPG-KEY-fedora
    ./etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-13-primary
    ./etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-i386
    ./etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-ppc
    ./etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-ppc64
    ./etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-x86_64
    ./etc/redhat-release
    ./etc/rpm/macros.dist
    ./etc/system-release
    ./etc/system-release-cpe
    ./etc/yum.repos.d
    ./etc/yum.repos.d/fedora-rawhide.repo
    ./etc/yum.repos.d/fedora-updates-testing.repo
    ./etc/yum.repos.d/fedora-updates.repo
    ./etc/yum.repos.d/fedora.repo
    ./usr/share/doc/fedora-release-13
    ./usr/share/doc/fedora-release-13/GPL
    57 blocks

    $ gpg etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-13-primary
    pub  4096R/E8E40FDE 2010-01-19 Fedora (13) <fedora@fedoraproject.org>

You may wish to do this in a tempoary directory to make cleaning it up easy.

fedoraproject.org
-----------------
One can simply browse to http://fedoraproject.org/keys to verify that the key
has been uploaded.

sigulsign_unsigned
------------------
The best way to test whether or not the key has been added correctly is to
sign a package using the key, like our newly built fedora-release package.

::

    $ ./sigulsign_unsigned.py fedora-13 fedora-release-13-0.3
    Passphrase for fedora-13: 

The command should exit cleanly.

Public key servers
------------------
One can use the <code>search-keys</code> command from gpg to locate the key on the public server:

::

    $ gpg --search-keys "Fedora (13)"
    gpg: searching for "Fedora (13)" from hkp server subkeys.pgp.net
    (1) Fedora (13) <fedora@fedoraproject.org>
          4096 bit RSA key E8E40FDE, created: 2010-01-19
    ...

Koji
----
Log into koji01 by way of gateway.fedoraproject.org.

Verify that ``/etc/koji-gc/koji-gc.conf`` has the new key in it.

Consider Before Running
=======================

Nothing at this time.

