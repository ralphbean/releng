================
Branching Freeze
================


Introduction/Background
=======================

When the next release is branched from rawhide, it initially composes much
like rawhide with nightly composes and no updates process.

Once the Alpha change freeze point is reached, bodhi is enabled for the
branched release and updates are required.

* Send announcement to devel-announce mailing list noting that the alpha
  change freeze is going to happen at least one day in advance.
* Make sure all packages are signed.
* ``FIXME - PUPPET IS GONE`` Enable check for signed packages in mash config
  in puppet.
* Koji tag changes here
* Bodhi changes here

.. note::
    For updates pushers:
        In Change freeze only updates that fix accepted blockers or Freeze
        break bugs are allowed into the main tree. Please coordinate with QA
        for any stable updates pushes. Otherwise ONLY push updates-testing.
