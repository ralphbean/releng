================
Multi Boot Media
================


Description
===========
Release Engineering is responsible for producing the final .ISO files for
custom spins that are approved by the Fedora Board. This also includes
Multi-Image DVD's such as the `Multi Desktop DVD`_

Action
======
The Multi Boot images are created with ``multiboot-media-creator.py``. Make
sure to get the latest version from the git repo.

::

    $ https://github.com/spotrh/multiboot-media-creator
    $ https://pagure.io/multiboot-media-creator

https://fedorahosted.org/rel-eng/ticket/6151

More info on the multiboot-media-creator tool is in the README file.

Multi Desktop DVD
-----------------

The `Multi Desktop DVD`_ combines all official desktop spins such as the Live
image, KDE, LXDE and Xfce. To create it, run

::

    $ su -c './multiboot-media-creator/multiboot-media-creator.py \
        -i Fedora-<xx>-{i686,x86_64}-Live-{Desktop,KDE,LXDE,XFCE}.iso \
        --bootdefault Fedora-<xx>-i686-Live-Desktop.iso \
        --target Fedora-<xx>-Multi-Boot.iso \
        --targetname Fedora-<xx>-Multi-Desktop'

Notes:

#. Replace ``<xx>`` with the desired Fedora Release and make sure the paths to
   the downloaded images match
#. The order of the images on the command line does not matter,
   ``multiboot-media-creator.py`` will sort them alphabetically
#. The default image should be ``Fedora-XX-i686-Live-Desktop.iso`` since GNOME
   is the default desktop and i686 will run on all hardware even if the CPU is
   not correctly detected.
#. ``--target`` is the name of the ISO, ``--targetname`` is the ISO label. It
   must not contain spaces.

Dual Arch Installer DVD
-----------------------

The EMEA Ambassdors decided they want to have one combined dual arch installer
image for Fedora 15 onwards. It is created with

::

    $ su -c './multiboot-media-creator/multiboot-media-creator.py \
        -i Fedora-<xx>-{i686,x86_64}-DVD.iso \
        --bootdefault Fedora-<xx>-i686-Live-DVD.iso \
        --target Fedora-<xx>-Multi-Install.iso \
        --targetname Fedora-<xx>-Multi-Install'

Verification
============
* Publish the image for testers to run the `relevant test cases`_.

Consider Before Running
=======================

* Download all images required.
* Download the checksums and check the individual images before creating the
  Multi Boot ISO because there is no verification available from the boot menu.
* Make sure you have enough disk space available to create the desired image.
* Make sure the resulting image fits on the target media. Normal DVDs can take
  up to 4,7 GB and 8,5 GB for Dual Layer.


.. _Multi Desktop DVD:
    https://fedoraproject.org/wiki/User:Cwickert/MultiDesktopDVD
.. _relevant test cases:
    https://fedoraproject.org/wiki/Test_Results:Fedora_15_Final_Multi_Image_DVD
