#!/usr/bin/python -tt
# vim: fileencoding=utf8
#
# find_FTBFS.py - Find FTBFS packages
#
# Authors:
#     Till Maas <opensource@till.name>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
import operator

import koji

branched_tag = 'f20'

f18_rebuild_start = '2012-07-17 14:18:03.000000'
f19_rebuild_start = '2013-07-25 00:00:00.000000'
f20_rebuild_start = '2013-07-25 00:00:00.000000'

epoch = f18_rebuild_start

kojihub = 'http://koji.fedoraproject.org/kojihub'
kojisession = koji.ClientSession(kojihub)

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
