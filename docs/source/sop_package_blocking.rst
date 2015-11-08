================
Package Blocking
================

Description
===========
If a `package is removed (retired) from Fedora`_, for example because it was
renamed, it needs to be blocked in Koji. This prevents creating new package
builds and distribution of built RPMs. Packages are blocked in the listing of
``tags``, due to inheritance it is enough to block packages at the oldest tag
will make it unavailable also in upstream tags.

Action
======
The blocking of retired packages is done by the `block_retired.py`_ script as
part of the daily Rawhide and Branched composes.


.. _package is removed (retired) from Fedora:
    https://fedoraproject.org/wiki/How_to_remove_a_package_at_end_of_life

.. _block_retired.py:
    https://pagure.io/releng/blob/master/f/scripts/block_retired.py
