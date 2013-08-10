#!/usr/bin/python
#
# find-unblocked-orphans.py - A utility to find orphaned packages in pkgdb
#                             that are unblocked in koji and to show what
#                             may require those orphans
#
# Copyright (c) 2009-2011 Red Hat
#
# Authors:
#     Jesse Keating <jkeating@redhat.com>
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

from collections import OrderedDict
import cPickle as pickle
import datetime
import os
from Queue import Queue
import sys
from threading import Thread

import fedora.client
import koji
import yum

# Set some variables
# Some of these could arguably be passed in as args.
# If this is pre-branch, these repos should be rawhide; otherwise,
# they should be branched.
DEFAULT_REPO = 'http://kojipkgs.fedoraproject.org/mash/rawhide/i386/os'
DEFAULT_SOURCE_REPO = \
    'http://kojipkgs.fedoraproject.org/mash/rawhide/source/SRPMS'
TAG = 'f20'  # tag to check in koji

# pre-branch, this should be 8 and 'devel'. Post-branch, you need
# to look it up via:
#  pkgdb = fedora.client.PackageDB()
#  list = pkgdb.get_collection_list()
# Will generally be 20-something and 'F-xx'
RAWHIDE_COLLECTION = 8  # pkgdb ID for the devel branch
RAWHIDE_BRANCHNAME = 'devel'  # pkgdb name for the devel branch

# pkgdb uid for orphan
ORPHAN_UID = 'orphan'

pkgdb = fedora.client.PackageDB()


def get_cache(filename,
              max_age=3600,
              cachedir='~/.cache',
              default=None):
    """ Get a pickle file from cache
    :param filename: Filename with pickle data
    :type filename: str
    :param max_age: Maximum age of cache in seconds
    :type max_age: int
    :param cachedir: Directory to get file from
    :type cachedir: str
    :param default: Default value if cache is too old or does not exist
    :type default: object
    :returns: pickled object
    """
    cache_file = os.path.expanduser(os.path.join(cachedir, filename))
    try:
        with open(cache_file, "rb") as pickle_file:
            mtime = os.fstat(pickle_file.fileno()).st_mtime
            mtime = datetime.datetime.fromtimestamp(mtime)
            now = datetime.datetime.now()
            if (now - mtime).total_seconds() < max_age:
                res = pickle.load(pickle_file)
            else:
                res = default
    except IOError:
        res = default
    return res


def write_cache(data, filename, cachedir='~/.cache'):
    """ Write ``data`` do pickle cache
    :param data: Data to cache
    :param filename: Filename for cache file
    :type filename: str
    :param cachedir: Dir for cachefile
    :type cachedir: str
    """
    cache_file = os.path.expanduser(os.path.join(cachedir, filename))
    with open(cache_file, "wb") as pickle_file:
        pickle.dump(data, pickle_file)


people_queue = Queue()
people_dict = get_cache("orphans-people.pickle", default={})


def _comaintainers(package, branch=RAWHIDE_BRANCHNAME):
    comaint = []
    pkginfo = pkgdb.get_package_info(package, branch=branch)
    users = pkginfo.packageListings[0]['people']
    for user in users:
        acl = user['aclOrder']
        # any user except orphan
        if acl['commit'] or acl['approveacls']:
            comaint.append(user['username'])
    return comaint


def people_worker():
    def get_people(package, branch=RAWHIDE_BRANCHNAME):
        pkginfo = pkgdb.get_package_info(package, branch=branch)
        pkginfo = pkginfo.packageListings[0]
        people_ = [pkginfo.owner]
        people_.extend(p['username'] for p in pkginfo['people'])
        return people_

    while True:
        package = people_queue.get()
        if package not in people_dict:
            people_ = get_people(package)
            people_dict[package] = people_
        people_queue.task_done()


def setup_yum(repo=DEFAULT_REPO, source_repo=DEFAULT_SOURCE_REPO):
    """ Setup YumBase with two repos
    This code was mostly stolen from
    http://yum.baseurl.org/wiki/YumCodeSnippet/SetupArbitraryRepo
    """

    yb = yum.YumBase()
    yb.preconf.init_plugins = False
    # FIXME: Maybe reuse should be False here
    if not yb.setCacheDir(force=True, reuse=True):
        print >> sys.stderr, "Can't create a tmp. cachedir. "
        sys.exit(1)

    yb.conf.cache = 0

    yb.repos.disableRepo('*')
    yb.add_enable_repo('repo', [repo])
    yb.add_enable_repo('repo-source', [source_repo])
    yb.arch.archlist.append('src')
    return yb

sys.stderr.write("Setting up yum...")
yb = setup_yum()
sys.stderr.write("done\n")


# This function was stolen from pungi
def SRPM(package):
    """Given a package object, get a package object for the
    corresponding source rpm. Requires yum still configured
    and a valid package object."""
    srpm = package.sourcerpm.split('.src.rpm')[0]
    (sname, sver, srel) = srpm.rsplit('-', 2)
    try:
        srpmpo = yb.pkgSack.searchNevra(name=sname,
                                        ver=sver,
                                        rel=srel,
                                        arch='src')[0]
        return srpmpo
    except IndexError:
        print >> sys.stderr, "Error: Cannot find a source rpm for %s" % srpm
        sys.exit(1)




def orphan_packages(collection_id=RAWHIDE_COLLECTION,
                    cache_filename='orphans.pickle'):
    orphans = get_cache(cache_filename, default=[])

    if orphans:
        return orphans
    else:
        pkgs = pkgdb.orphan_packages()

        sys.stderr.write('Getting comaintainers...\n')
        # Reduce to packages orphaned on devel
        for p in pkgs:
            for listing in p['listings']:
                if listing['collectionid'] == collection_id:
                    # statuscode cheatsheet:
                    # 14 orphaned
                    # 20 deprecated
                    if listing['owner'] == ORPHAN_UID and \
                            listing['statuscode'] == 14:
                        orphans.append(p['name'])
            try:
                write_cache(orphans, cache_filename)
            except IOError, e:
                sys.stderr.write("Caching of orphans failed: {0}\n".format(e))
        return orphans


def unblocked_packages(packages, tagID=TAG):
    unblocked = []
    kojisession = koji.ClientSession('https://koji.fedoraproject.org/kojihub')

    kojisession.multicall = True
    for p in packages:
        kojisession.listPackages(tagID=tagID, pkgID=p, inherited=True)
    listings = kojisession.multiCall()

    # Check the listings for unblocked packages.
    for [pkg] in listings:
        if not pkg[0]['blocked']:
            package_name = pkg[0]['package_name']
            people_queue.put(package_name)
            unblocked.append(package_name)
    return unblocked


class BinSrcMapper(object):
    def __init__(self):
        self._src_by_bin = None
        self._bin_by_src = None

    def create_mapping(self):
        src_by_bin = {}  # Dict of source pkg objects by binary package objects
        bin_by_src = {}  # Dict of binary pkgobjects by srpm name
        all_packages = yb.pkgSack.returnPackages()

        # Populate the dicts
        for rpm_package in all_packages:
            if rpm_package.arch == 'src':
                continue
            srpm = SRPM(rpm_package)
            src_by_bin[rpm_package] = srpm
            if srpm.name in bin_by_src:
                bin_by_src[srpm.name].append(rpm_package)
            else:
                bin_by_src[srpm.name] = [rpm_package]

        self._src_by_bin = src_by_bin
        self._bin_by_src = bin_by_src

    @property
    def by_src(self):
        if not self._bin_by_src:
            self.create_mapping()
        return self._bin_by_src

    @property
    def by_bin(self):
        if not self._src_by_bin:
            self.create_mapping()
        return self._src_by_bin

sys.stderr.write("Setting up packager mapper...")
package_mapper = BinSrcMapper()
sys.stderr.write("done\n")


def dependent_packages(name, ignore):
    """ Return dependent packages for package ``name`` that are built from
        different SPECS or that shall be ignored
        :param ignore: list of names
        :type ignore: list() of str()

        :returns: OrderedDict dependent_package: list of requires only provided
                  by package ``name``
                  {dep_pkg: [prov, ...]}
    """
    provides = []
    dep_packages = {}
    # Generate a dict of orphans to things requiring them and why
    # Some of this code was stolen from repoquery
    try:  # We may have some orphans that aren't in the repo
        for pkg in package_mapper.by_src[name]:
            # add all the provides from the package as strings
            string_provides = [yum.misc.prco_tuple_to_string(prov)
                               for prov in pkg.provides]
            provides.extend(string_provides)

            # add all files as provides
            # pkg.files is a dict with keys like "file" and "dir"
            # values are a list of file/dir paths
            for paths in pkg.files.itervalues():
                # sometimes paths start with "//" instead of "/"
                # normalise "//" to "/":
                # os.path.normpath("//") == "//", but
                # os.path.normpath("///") == "/"
                file_provides = [os.path.normpath('//%s' % fn)
                                 for fn in paths]
                provides.extend(file_provides)

        # Zip through the provides and find what's needed
        for prov in provides:
            # check only base provide, ignore specific versions
            # "foo = 1.fc20" -> "foo"
            base_provide = prov.split()[0]

            # Elide provide if also provided by another package
            for pkg in yb.pkgSack.searchProvides(base_provide):
                # FIXME: might miss broken in case the other provider
                # depends on a to-be-removed package as well
                if pkg.name not in ignore:
                    break
            else:
                for dependent_pkg in yb.pkgSack.searchRequires(base_provide):
                    # skip if the dependent rpm package belongs to the
                    # to-be-removed Fedora package
                    if dependent_pkg in package_mapper.by_src[name]:
                        continue

                    # skip if the dependent rpm package is also a
                    # package that should be removed
                    if dependent_pkg.name in ignore:
                        continue

                    # use setdefault to either create an entry for the
                    # dependent package or add the required prov
                    dep_packages.setdefault(dependent_pkg, set()).add(prov)
    except KeyError:
        # If we don't have a package in the repo, there is nothing to do
        sys.stderr.write("package %s not found in repo\n".format(name))
    return OrderedDict(sorted(dep_packages.items()))


def main():
    failed = sys.argv[1:]
    # list of orphans on the devel branch from pkgdb
    sys.stderr.write('Contacting pkgdb for list of orphans...')
    orphans = orphan_packages()
    sys.stderr.write('done\n')

    # Start threads to get information about (co)maintainers for packages
    for i in range(0, 2):
        people_thread = Thread(target=people_worker)
        people_thread.daemon = True
        people_thread.start()
    # keep pylint silent
    del i

    sys.stderr.write('Getting builds from koji...')
    unblocked = unblocked_packages(sorted(orphans + failed))
    sys.stderr.write('done\n')

    sys.stderr.write('Calculating dependencies...\n')
    # Create yum object and depsolve out if requested.
    # TODO: add app args to either depsolve or not

    # get a list of all rpm_pkgs that are to be removed
    rpm_pkg_names = []
    for name in unblocked:
        # Empty list if pkg is only for a different arch
        bin_pkgs = package_mapper.by_src.get(name, [])
        rpm_pkg_names.extend([p.name for p in bin_pkgs])

    # dict for all dependent package for each to-be-removed package
    dep_map = OrderedDict()
    for name in unblocked:
        ignore = rpm_pkg_names
        dep_map[name] = OrderedDict()
        while True:
            to_check = [name]
            dep_packages = dependent_packages(to_check.pop(), ignore)
            if dep_packages:
                new_names = []
                new_srpm_names = set()
                for pkg, dependencies in dep_packages.items():
                    new_names.append(pkg.name)
                    if pkg.arch != "src":
                        srpm_name = package_mapper.by_bin[pkg].name
                    else:
                        srpm_name = pkg.name
                    new_srpm_names.add(srpm_name)

                    for dep in dependencies:
                        dep_map[name].setdefault(srpm_name, OrderedDict()).setdefault(pkg, set()).add(dep)

                for srpm_name in new_srpm_names:
                    people_queue.put(srpm_name)

                ignore.extend(new_names)
                to_check.extend(new_names)
            if not to_check:
                break

    sys.stderr.write("Waiting for (co)maintainer information...")
    people_queue.join()
    sys.stderr.write("done\n")
    write_cache(people_dict, "orphans-people.pickle")

    for package_name in unblocked:
        #reason = package_name in orphans and "orphan" or "fails to build"
        p = ', '.join(people_dict[package_name])
        print "{0} {1}".format(package_name, p)

    print "\nDependent packages:"
    for name, subdict in dep_map.items():
        if subdict:
            print "\nRemoving: %s" % name
            for fedora_package, dep_packages in subdict.items():
                p = ", ".join(people_dict[fedora_package])
                print "\t {0} {1}".format(fedora_package, p)
                for dep in dep_packages:
                    provides = ", ".join(sorted(dep_packages[dep]))
                    print "\t\t%s requires %s" % (dep.name, provides)

    # Pointer to this script
    print '\nThe script creating this output is run and developed by Fedora'
    print 'Release Engineering. Please report issues at its trac instance:'
    print 'https://fedorahosted.org/rel-eng/'
    print 'The sources of this script can be found at:'
    print 'https://git.fedorahosted.org/cgit/releng/tree/scripts/find-unblocked-orphans.py'


if __name__ == "__main__":
    main()
