#!/usr/bin/python -tt
# vim: fileencoding=utf8
#
# find_FTBFS.py - Find FTBFS packages
#
# SPDX-License-Identifier:	GPL-2.0
#
# Authors:
#     Till Maas <opensource@till.name>
#
import argparse
import operator

import koji

branched_tag = 'f23'

f18_rebuild_start = '2012-07-17 14:18:03.000000'
f19_rebuild_start = '2013-02-12 00:00:00.000000'
f20_rebuild_start = '2013-07-25 00:00:00.000000'
f21_rebuild_start = '2013-06-06 00:00:00.000000'
# no F22 rebuild
f23_rebuild_start = '2015-06-16 00:00:00.000000'

epoch = f21_rebuild_start

kojihub = 'https://koji.fedoraproject.org/kojihub'
kojisession = koji.ClientSession(kojihub)

parser = argparse.ArgumentParser()
parser.add_argument("packages", nargs="*", metavar="package",
                    help="if specified, only check whether the specified "
                         "packages were not rebuild")

args = parser.parse_args()

if args.packages:
    all_koji_pkgs = args.packages
else:
    all_koji_pkgs = kojisession.listPackages(branched_tag, inherited=True)

unblocked = sorted([pkg for pkg in all_koji_pkgs if not pkg['blocked']],
                   key=operator.itemgetter('package_name'))

kojisession.multicall = True
for pkg in unblocked:
    kojisession.listBuilds(pkg['package_id'], state=1, createdAfter=epoch)

builds = kojisession.multiCall()

package_map = zip(unblocked, builds)
name_map = [(x['package_name'], b) for (x, b) in package_map]

# packages with no builds since epoch
unbuilt = [x for (x, b) in name_map if b == [[]]]

# remove packages that have never build, e.g. EPEL-only packages
kojisession.multicall = True
for pkg_name in unbuilt:
    kojisession.getLatestRPMS(branched_tag, pkg_name)

last_builds = kojisession.multiCall()
last_builds_map = zip(unbuilt, last_builds)
ftbfs = [p for p, b in last_builds_map if b != [[[], []]]]

print " ".join(ftbfs)
