.. _philosophy:

=====================================
Fedora Release Engineering Philosophy
=====================================

Being an official part of Fedora means that it is composed and supported by
Fedora Release Engineering (releng). Releng bestows this status on items that
successfully makes its way through our Manufacturing Train and satisfies all
related policies. With this status the item is Open, Integrated, Reproducible,
Auditable, Definable, and Deliverable. (in no particular order)
This document provides definitions for each of those terms, why they're
important, and how we guarantee them. All parts of Fedora should strive to be
meet all parts of being official at all times.

Open
====

It goes without saying that Fedora is built on `the four F's`_. In releng we are
no different, we require everything be open, that is open source, developed in
the open, available for all to look at, use and contribute to. All downstreams
should be able to take our tooling and make their own derivative of Fedora,
either by rebuilding everything, perhaps with different otions or just adding
thier own marks and packages and recomposing. At any time anyone should be able
to see how Fedora is put together and put together their own version of Fedora.

Integrated
==========

Fedora is a huge project with a massive number of ever growing deliverables.
This means when we add new deliverables we need to have the composing of them
tightly integrated into the process. We ship Fedora a whole unit, so we need to
make it as a whole unit. Any new tooling we use needs to be consistent with the
existing tooling in how it works. The tooling has to ensure that the output is
Reproducible, Auditable, Definable so that it can be Deliverable.

Reproducible
============

A reproducible component is one we can rebuild from scratch at any time with
less than a day's worth of effort. It implies we can look up all of the source
code, and know exactly what revisions to use from source control. We know
exactly what tools are used in the build environment to transform the source
code into product content (binaries). We also know how to reproduce the same
build environment to ensure the tools behave like we expect. This aspect is why
releng is in the business of standardizing on build tools.

Reproducible components are important because they make them a lot easier to
maintain. The Security Team takes advantage of this aspect of an Product. Not
knowing how to rebuild a subsystem in a product to apply security fixes, or
bug fixes, makes their job much more difficult. It would be a significant risk
to provide a product to users that we are incapable (or merely unsure) of how
to build again. Not knowing the origin of source code is also a significant
risk, which is why many of our build environments are configured to prevent
tools from dynamically downloading content from the internet.

The combination of Koji and fedpkg is what enables releng to rebuild a
component. fedpkg manages the source code in our dist-git system, and Koji
archives details about the build environment, the tools used, logs, and of
course the binaries themselves. The reproducibility aspect of a product is
the primary reason we require all products be built in Koji if they seek to be
an officially supported part of Fedora.

Auditable
=========

Fedora and Red Hat expect auditable output too, which means releng knows who
built what, when, and where (and how, but that's reproducibility). Being able
to authoritatively say that something was built within Fedora by people who
have signed the FPCA is important for several reasons. One big reason is it
promotes and fosters accountability within the comunity. It promotes ownership.
Another one is more defensive: in the event of a security breach, we have a
lot of evidence and data prepared to help us identify what content (if any) was
compromised. If a kernel RPM randomly shows up, and we have no records of
building it and/or shipping it, that should raise a lot of alarms pretty
quickly!

Red Hat's Infosec team and Fedora Security care about this aspect deeply. We
should never be in a position where we cannot definitively answer why a piece
of content is available to users. This aspect is also a key part of the
verification that is done when Fedora becomes RHEL. All downstream consumers of
Fedora expect that they can verify the code and binaries that they consume
from Fedora.

Releng tracks this data in 2 systems, 1 of which we own: Koji and Bodhi. Koji
uses ssl certs tied to FAS and bodhi uses FAS for authentication to provide a
strong relationship between a user and the content. Koji builds the content of
course, the Bodhi tracks the bugs, documentation, and enhancements associated
with the content and actually does the delivery. Bodhi maintains records of
what was shipped when and where, and who pushed it.

Definable
=========

The ability to define and predict content is necessary as well. It is important
to know exactly what was included in a release. It helps protect against
shipping content that unnecessarily causes a support burden. This aspect of a
Fedora component helps support other aspects like reproducibility. No need to
reproduce software we do not have to ship, right? Ensuring the product content
is lean and trim may sound obvious, but in the world of sprawling RPM
dependencies, Maven artifacts, and Ruby gems, it is actually rather easy to
include content during the course of a multi-month or multi-year development
cycle.

Furthermore, a definable component has the changes made to it vetted and
understood by multiple teams. They are not made in an ad-hoc manor or without
consent from FESCo, QA, releng, and the Product Working Groups that contribute
at the program level. This reduces change risk to the user, which our users
and downstreams like to hear.

Many systems help make components definable. Releng uses Bugzilla, trac,
blocker bugs and bodhi to track additions and changes.

Deliverable
===========

Official parts of Fedora are eligible to be delivered to ``/pub/fedora/`` or
``/pub/alt/releases`` on `Fedora Download`_ and to get `mirrorlists`_ in
`mirrormanager`_. These Distribution Platforms are maintained by Fedora
Infrastructure and releng. This is not a feature of the product content itself
or how it was built, but rather how it was delivered to users through releng's
processes. Those platforms are geographically replicated by the volunteer
mirror network. They provide a reliable and durable service that ensures users
can always reach Fedora for updates, even in the event of a disaster affecting
our data center in phx2.

User support (user mailing lists and `#fedora`) and Fedora Security team depend
on these services. It is vital to that critical security fixes and updates are
always available to users.

.. _the four F's: https://fedoraproject.org/wiki/Foundations
.. _Fedora Download: https://dl.fedoraproject.org/pub/
.. _mirrorlists: https://admin.fedoraproject.org/mirrormanager
.. _mirrormanager: https://fedorahosted.org/mirrormanager/
