#!/usr/bin/python
#
# find_unblocked_orphans.py - A utility to find orphaned packages in pkgdb
#                             that are unblocked in koji and to show what
#                             may require those orphans
#
# Copyright (c) 2009-2013 Red Hat
# SPDX-License-Identifier:	GPL-2.0
#
# Authors:
#     Jesse Keating <jkeating@redhat.com>
#     Till Maas <opensource@till.name>

from Queue import Queue
from collections import OrderedDict
from threading import Thread
import argparse
import cPickle as pickle
import datetime
import email.mime.text
import hashlib
import os
import smtplib
import sys
import textwrap

import koji
import pkgdb2client
import yum

try:
    import texttable
    with_table = True
except ImportError:
    with_table = False


EPEL5_RELEASE = dict(
    repo='https://kojipkgs.fedoraproject.org/mash/updates/el5-epel/x86_64/',
    source_repo='https://kojipkgs.fedoraproject.org/mash/updates/'
    'el5-epel/SRPMS',
    tag='dist-5E-epel',
    branch='el5',
    mailto='epel-devel@lists.fedoraproject.org',
)

EPEL6_RELEASE = dict(
    repo='https://kojipkgs.fedoraproject.org/mash/updates/el6-epel/x86_64/',
    source_repo='https://kojipkgs.fedoraproject.org/mash/updates/'
    'el6-epel/SRPMS',
    tag='dist-6E-epel',
    branch='el6',
    mailto='epel-devel@lists.fedoraproject.org',
)

EPEL7_RELEASE = dict(
    repo='https://kojipkgs.fedoraproject.org/mash/updates/epel7/x86_64/',
    source_repo='https://kojipkgs.fedoraproject.org/mash/updates/epel7/SRPMS',
    tag='epel7',
    branch='epel7',
    mailto='epel-devel@lists.fedoraproject.org',
)

RAWHIDE_RELEASE = dict(
    repo='https://kojipkgs.fedoraproject.org/mash/rawhide/i386/os',
    source_repo='https://kojipkgs.fedoraproject.org/mash/rawhide/source/SRPMS',
    tag='f22',
    branch='master',
    mailto='devel@lists.fedoraproject.org',
)

BRANCHED_RELEASE = dict(
    repo='https://kojipkgs.fedoraproject.org/mash/branched/i386/os',
    source_repo='https://kojipkgs.fedoraproject.org/mash/branched/source/'
                'SRPMS',
    tag='f21',
    branch='f21',
    mailto='devel@lists.fedoraproject.org',
)

RELEASES = {
    "rawhide": RAWHIDE_RELEASE,
    "branched": BRANCHED_RELEASE,
    "epel7": EPEL7_RELEASE,
    "epel6": EPEL6_RELEASE,
    "epel5": EPEL5_RELEASE,
}

# pkgdb uid for orphan
ORPHAN_UID = 'orphan'

HEADER = """The following packages are orphaned or did not build for two
releases and will be retired when Fedora ({}) is branched, unless someone
adopts them. If you know for sure that the package should be retired, please do
so now with a proper reason:
https://fedoraproject.org/wiki/How_to_remove_a_package_at_end_of_life

According to https://fedoraproject.org/wiki/Schedule branching will
occur not earlier than 2014-07-08. The packages will be retired shortly before.
"""

HEADER = """The following packages are orphaned and will be retired when they
are orphaned for six weeks, unless someone adopts them. If you know for sure
that the package should be retired, please do so now with a proper reason:
https://fedoraproject.org/wiki/How_to_remove_a_package_at_end_of_life

Note: If you received this mail directly you (co)maintain one of the affected
packages or a package that depends on one. Please adopt the affected package or
retire your depending package to avoid broken dependencies, otherwise your
package will be retired when the affected package gets retired.
"""

FOOTER = """-- \nThe script creating this output is run and developed by Fedora
Release Engineering. Please report issues at its trac instance:
https://fedorahosted.org/rel-eng/
The sources of this script can be found at:
https://git.fedorahosted.org/cgit/releng/tree/scripts/find_unblocked_orphans.py
"""


def send_mail(from_, to, subject, text, bcc=None):
    if bcc is None:
        bcc = []

    msg = email.mime.text.MIMEText(text)
    msg["Subject"] = subject
    msg["From"] = from_
    msg["To"] = to
    if isinstance(to, basestring):
        to = [to]
    smtp = smtplib.SMTP('127.0.0.1')
    errors = smtp.sendmail(from_, to + bcc, msg.as_string())
    smtp.quit()
    return errors


pkgdb = pkgdb2client.PkgDB()


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


class PKGDBInfo(object):
    def __init__(self, package, branch=RAWHIDE_RELEASE["branch"]):
        self.package = package
        self.branch = branch

        try:
            pkginfo = pkgdb.get_package(package, branches=branch)
        except Exception as e:
            sys.stderr.write(
                "Error getting pkgdb info for {} on {}\n".format(
                    package, branch))
            # FIXME: Write proper traceback
            sys.stderr.write(str(e))
            self.pkginfo = None
            return

        self.pkginfo = pkginfo["packages"][0]

    def get_people(self):
        def associated(pkginfo, exclude=None):
            """

            :param exclude: People to exclude, e.g. the point of contact.
            :type exclude: list
            """
            other_people = set()
            for acl in pkginfo.get("acls", []):
                if acl["status"] == "Approved":
                    fas_name = acl["fas_name"]
                    if fas_name != "group::provenpackager" and \
                            fas_name not in exclude:
                        other_people.add(fas_name)
            return sorted(other_people)

        if self.pkginfo is not None:
            people_ = [self.pkginfo["point_of_contact"]]
            people_.extend(associated(self.pkginfo, exclude=people_))
            return people_
        else:
            return []

    @property
    def age(self):
        now = datetime.datetime.utcnow()
        age = now - self.status_change
        return age

    @property
    def status_change(self):
        status_change = self.pkginfo["status_change"]
        status_change = datetime.datetime.utcfromtimestamp(status_change)
        return status_change

    def __getitem__(self, *args, **kwargs):
        return self.pkginfo.__getitem__(*args, **kwargs)


def setup_yum(repo=RAWHIDE_RELEASE["repo"],
              source_repo=RAWHIDE_RELEASE["source_repo"]):
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
    # use digest to make repo id unique for each URL
    yb.add_enable_repo('repo-' + hashlib.sha256(repo).hexdigest(), [repo])
    yb.add_enable_repo('repo-source-' + hashlib.sha256(repo).hexdigest(),
                       [source_repo])
    yb.arch.archlist.append('src')
    return yb


def orphan_packages(branch=RAWHIDE_RELEASE["branch"]):
    cache_filename = 'orphans-{}.pickle'.format(branch)
    orphans = get_cache(cache_filename, default={})

    if orphans:
        return orphans
    else:
        pkgdbresponse = pkgdb.get_packages(
            "", orphaned=True, branches=branch, page="all")
        pkgs = pkgdbresponse["packages"]
        for p in pkgs:
            orphans[p["name"]] = p
        try:
            write_cache(orphans, cache_filename)
        except IOError, e:
            sys.stderr.write("Caching of orphans failed: {0}\n".format(e))
        return orphans


def unblocked_packages(packages, tagID=RAWHIDE_RELEASE["tag"]):
    unblocked = []
    kojisession = koji.ClientSession('https://koji.fedoraproject.org/kojihub')

    kojisession.multicall = True
    for p in packages:
        kojisession.listPackages(tagID=tagID, pkgID=p, inherited=True)
    listings = kojisession.multiCall()

    # Check the listings for unblocked packages.

    for pkgname, result in zip(packages, listings):
        if isinstance(result, list):
            [pkg] = result
            if not pkg[0]['blocked']:
                package_name = pkg[0]['package_name']
                unblocked.append(package_name)
        else:
            print "ERROR: {pkgname}: {error}".format(
                pkgname=pkgname, error=result)
    return unblocked


class DepChecker(object):
    def __init__(self, release):
        self._src_by_bin = None
        self._bin_by_src = None
        self.release = release
        yumbase = setup_yum(repo=RELEASES[release]["repo"],
                            source_repo=RELEASES[release]["source_repo"])
        self.yumbase = yumbase
        self.pkgdbinfo_queue = Queue()
        self.pkgdb_cache = "orphans-pkgdb-{}.pickle".format(release)
        self.pkgdb_dict = get_cache(self.pkgdb_cache, default={})
        self.not_in_repo = []

    def create_mapping(self):
        src_by_bin = {}  # Dict of source pkg objects by binary package objects
        bin_by_src = {}  # Dict of binary pkgobjects by srpm name
        all_packages = self.yumbase.pkgSack.returnPackages()

        # Populate the dicts
        for rpm_package in all_packages:
            if rpm_package.arch == 'src':
                continue
            srpm = self.SRPM(rpm_package)
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

    def find_dependent_packages(self, srpmname, ignore):
        """ Return packages depending on packages built from SRPM ``srpmname``
            that are built from different SRPMS not specified in ``ignore``.

            :param ignore: list of SRPMs of packages that will not be returned
                as dependent packages.
            :type ignore: list() of str()

            :returns: OrderedDict dependent_package: list of requires only
                provided by package ``srpmname`` {dep_pkg: [prov, ...]}
        """
        # Some of this code was stolen from repoquery
        dependent_packages = {}

        # Handle packags not found in the repo
        try:
            rpms = self.by_src[srpmname]
        except KeyError:
            # If we don't have a package in the repo, there is nothing to do
            sys.stderr.write(
                "Package {0} not found in repo\n".format(srpmname))
            self.not_in_repo.append(srpmname)
            rpms = []

        # provides of all packages built from ``srpmname``
        provides = []
        for pkg in rpms:
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
            for pkg in self.yumbase.pkgSack.searchProvides(base_provide):
                # FIXME: might miss broken dependencies in case the other
                # provider depends on a to-be-removed package as well
                if pkg.sourcerpm.rsplit('-', 2)[0] not in ignore:
                    break
            else:
                for dependent_pkg in self.yumbase.pkgSack.searchRequires(
                        base_provide):
                    # skip if the dependent rpm package belongs to the
                    # to-be-removed Fedora package
                    if dependent_pkg in self.by_src[srpmname]:
                        continue

                    # skip if the dependent rpm package is also a
                    # package that should be removed
                    if dependent_pkg.name in ignore:
                        continue

                    # use setdefault to either create an entry for the
                    # dependent package or add the required prov
                    dependent_packages.setdefault(dependent_pkg, set()).add(
                        prov)
        return OrderedDict(sorted(dependent_packages.items()))

    def pkgdb_worker(self):
        branch = RELEASES[self.release]["branch"]
        while True:
            package = self.pkgdbinfo_queue.get()
            if package not in self.pkgdb_dict:
                pkginfo = PKGDBInfo(package, branch)
                self.pkgdb_dict[package] = pkginfo
            self.pkgdbinfo_queue.task_done()

    def recursive_deps(self, packages, max_deps=20):
        # Start threads to get information about (co)maintainers for packages
        for i in range(0, 2):
            people_thread = Thread(target=self.pkgdb_worker)
            people_thread.daemon = True
            people_thread.start()
        # keep pylint silent
        del i
        # get a list of all rpm_pkgs that are to be removed
        rpm_pkg_names = []
        for name in packages:
            self.pkgdbinfo_queue.put(name)
            # Empty list if pkg is only for a different arch
            bin_pkgs = self.by_src.get(name, [])
            rpm_pkg_names.extend([p.name for p in bin_pkgs])

        # dict for all dependent packages for each to-be-removed package
        dep_map = OrderedDict()
        for name in sorted(packages):
            sys.stderr.write("Checking: {0}\n".format(name))
            ignore = rpm_pkg_names
            dep_map[name] = OrderedDict()
            to_check = [name]
            allow_more = True
            seen = []
            while True:
                sys.stderr.write("to_check ({}): {}\n".format(len(to_check),
                                                              repr(to_check)))
                check_next = to_check.pop()
                seen.append(check_next)
                dependent_packages = self.find_dependent_packages(check_next,
                                                                  ignore)
                if dependent_packages:
                    new_names = []
                    new_srpm_names = set()
                    for pkg, dependencies in dependent_packages.items():
                        if pkg.arch != "src":
                            srpm_name = self.by_bin[pkg].name
                        else:
                            srpm_name = pkg.name
                        if srpm_name not in to_check and \
                                srpm_name not in new_names and \
                                srpm_name not in seen:
                            new_names.append(srpm_name)
                        new_srpm_names.add(srpm_name)

                        for dep in dependencies:
                            dep_map[name].setdefault(
                                srpm_name,
                                OrderedDict()
                            ).setdefault(pkg, set()).add(dep)

                    for srpm_name in new_srpm_names:
                        self.pkgdbinfo_queue.put(srpm_name)

                    ignore.extend(new_names)
                    if allow_more:
                        to_check.extend(new_names)
                        dep_count = len(set(dep_map[name].keys() + to_check))
                        if dep_count > max_deps:
                            allow_more = False
                            to_check = to_check[0:max_deps]
                if not to_check:
                    break
            if not allow_more:
                sys.stderr.write("More than {0} broken deps for package"
                                 "'{1}', dependency check not"
                                 " completed\n".format(max_deps, name))

        sys.stderr.write("Waiting for (co)maintainer information...")
        self.pkgdbinfo_queue.join()
        sys.stderr.write("done\n")
        write_cache(self.pkgdb_dict, self.pkgdb_cache)
        return dep_map

    # This function was stolen from pungi
    def SRPM(self, package):
        """Given a package object, get a package object for the
        corresponding source rpm. Requires yum still configured
        and a valid package object."""
        srpm = package.sourcerpm.split('.src.rpm')[0]
        (sname, sver, srel) = srpm.rsplit('-', 2)
        try:
            srpmpo = self.yumbase.pkgSack.searchNevra(name=sname,
                                                      ver=sver,
                                                      rel=srel,
                                                      arch='src')[0]
            return srpmpo
        except IndexError:
            sys.stderr.write(
                "Error: Cannot find a source rpm for {}\n".format(srpm))
            sys.exit(1)


def maintainer_table(packages, pkgdb_dict):
    affected_people = {}

    if with_table:
        table = texttable.Texttable(max_width=80)
        table.header(["Package", "(co)maintainers", "Status Change"])
        table.set_cols_align(["l", "l", "l"])
        table.set_deco(table.HEADER)
    else:
        table = ""

    for package_name in packages:
        pkginfo = pkgdb_dict[package_name]
        people = pkginfo.get_people()
        for p in people:
            affected_people.setdefault(p, set()).add(package_name)
        p = ', '.join(people)
        age = pkginfo.age
        agestr = "{} weeks ago".format(age.days / 7)

        if with_table:
            table.add_row([package_name, p, agestr])
        else:
            table += "{} {} {}\n".format(package_name, p, agestr)

    if with_table:
        table = table.draw()
    return table, affected_people


def dependency_info(dep_map, affected_people, pkgdb_dict):
    info = ""
    for package_name, subdict in dep_map.items():
        if subdict:
            pkginfo = pkgdb_dict[package_name]
            status_change = pkginfo.status_change.strftime("%Y-%m-%d")
            age = pkginfo.age.days / 7
            fmt = "Depending on: {} ({}), status change: {} ({} weeks ago)\n"
            info += fmt.format(package_name, len(subdict.keys()),
                               status_change, age)
            for fedora_package, dependent_packages in subdict.items():
                people = pkgdb_dict[fedora_package].get_people()
                for p in people:
                    affected_people.setdefault(p, set()).add(package_name)
                p = ", ".join(people)
                info += "\t{0} (maintained by: {1})\n".format(fedora_package,
                                                              p)
                for dep in dependent_packages:
                    provides = ", ".join(sorted(dependent_packages[dep]))
                    info += "\t\t%s requires %s\n" % (dep.nvra, provides)
                info += "\n"
            info += "\n"
    return info


def maintainer_info(affected_people):
    info = ""
    for person in sorted(affected_people.iterkeys()):
        packages = affected_people[person]
        if person == ORPHAN_UID:
            continue
        info += "{0}: {1}\n".format(person, ", ".join(packages))
    return info


def package_info(unblocked, dep_map, depchecker, orphans=None, failed=None,
                 week_limit=6):
    info = ""
    pkgdb_dict = depchecker.pkgdb_dict

    table, affected_people = maintainer_table(unblocked, pkgdb_dict)
    info += table
    info += "\n\nThe following packages require above mentioned packages:\n"
    info += dependency_info(dep_map, affected_people, pkgdb_dict)

    info += "Affected (co)maintainers\n"
    info += maintainer_info(affected_people)

    wrapper = textwrap.TextWrapper(
        break_long_words=False, subsequent_indent="    ",
        break_on_hyphens=False
    )

    def wrap_and_format(label, pkgs):
        count = len(pkgs)
        text = "{} ({}): {}".format(label, count, " ".join(pkgs))
        wrappedtext = "\n" + wrapper.fill(text) + "\n\n"
        return wrappedtext

    if orphans:
        orphans = [o for o in orphans if o in unblocked]
        info += wrap_and_format("Orphans", orphans)

        orphans_breaking_deps = [o for o in orphans if
                                 o in dep_map and dep_map[o]]
        info += wrap_and_format("Orphans (dependend on)",
                                orphans_breaking_deps)

        orphans_breaking_deps_stale = [
            o for o in orphans_breaking_deps if
            (pkgdb_dict[o].age.days / 7) >= week_limit]

        info += wrap_and_format(
            "Orphans for at least {} weeks (dependend on)".format(week_limit),
            orphans_breaking_deps_stale)

        orphans_not_breaking_deps = [o for o in orphans if
                                     o not in dep_map or not dep_map[o]]

        info += wrap_and_format("Orphans (not depended on)",
                                orphans_not_breaking_deps)

        orphans_not_breaking_deps_stale = [
            o for o in orphans_not_breaking_deps if
            (pkgdb_dict[o].age.days / 7) >= week_limit]

        info += wrap_and_format(
            "Orphans for at least {} weeks (not dependend on)".format(
                week_limit),
            orphans_not_breaking_deps_stale)

    breaking = set()
    for package, deps in dep_map.items():
        breaking = breaking.union(set(deps.keys()))

    if breaking:
        info += wrap_and_format("Depending packages", sorted(breaking))

        if orphans:
            stale_breaking = set()
            for package in orphans_breaking_deps_stale:
                stale_breaking = stale_breaking.union(
                    set(dep_map[package].keys()))
            info += wrap_and_format(
                "Packages depending on packages orphaned for more than "
                "{} weeks".format(week_limit), sorted(stale_breaking))

    if failed:
        info += "\nFTBFS: " + " ".join(failed)
        info += "\n"
        ftbfs_breaking_deps = [o for o in failed if
                               o in dep_map and dep_map[o]]
        info += "FTBFS (depended on): " + " ".join(ftbfs_breaking_deps)
        info += "\n\n"
        ftbfs_not_breaking_deps = [o for o in failed if
                                   o not in dep_map or not dep_map[o]]
        info += "FTBFS (not depended on): " + " ".join(
            ftbfs_not_breaking_deps)
        info += "\n\n"

    if depchecker.not_in_repo:
        info += wrap_and_format("Not found in repo",
                                sorted(depchecker.not_in_repo))

    addresses = ["{0}@fedoraproject.org".format(p)
                 for p in affected_people.keys() if p != ORPHAN_UID]
    return info, addresses


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-orphans", dest="skip_orphans",
                        help="Do not look for orphans",
                        default=False, action="store_true")
    parser.add_argument("--release", choices=RELEASES.keys(),
                        default="rawhide")
    parser.add_argument("--mailto", default=None,
                        help="Send mail to this address (for testing)")
    parser.add_argument(
        "--send", default=False, action="store_true",
        help="Actually send mail including Bcc addresses to mailing list"
    )
    parser.add_argument("--mailfrom", default="nobody@fedoraproject.org")
    parser.add_argument("failed", nargs="*",
                        help="Additional packages, e.g. FTBFS packages")
    args = parser.parse_args()
    failed = args.failed

    if args.skip_orphans:
        orphans = []
    else:
        # list of orphans on the devel branch from pkgdb
        sys.stderr.write('Contacting pkgdb for list of orphans...')
        orphans = sorted(orphan_packages(RELEASES[args.release]["branch"]))
        sys.stderr.write('done\n')

    sys.stderr.write('Getting builds from koji...')
    unblocked = unblocked_packages(sorted(list(set(list(orphans) + failed))))
    sys.stderr.write('done\n')

    text = HEADER.format(RELEASES[args.release]["tag"].upper())
    sys.stderr.write("Setting up dependency checker...")
    depchecker = DepChecker(args.release)
    sys.stderr.write("done\n")
    sys.stderr.write('Calculating dependencies...')
    # Create yum object and depsolve out if requested.
    # TODO: add app args to either depsolve or not
    dep_map = depchecker.recursive_deps(unblocked)
    sys.stderr.write('done\n')
    info, addresses = package_info(unblocked, dep_map, depchecker,
                                   orphans=orphans, failed=failed)
    text += "\n"
    text += info
    text += FOOTER
    print text

    if args.mailto or args.send:
        subject = "Orphaned packages in " + args.release
        if args.mailto:
            mailto = args.mailto
        else:
            mailto = RELEASES[args.release]["mailto"]
        if args.send:
            bcc = addresses
        else:
            bcc = None
        mail_errors = send_mail(args.mailfrom, mailto, subject, text, bcc)
        if mail_errors:
            sys.stderr.write("mail errors: " + repr(mail_errors) + "\n")

    sys.stderr.write("Addresses ({}): {}\n".format(len(addresses),
                                                   ", ".join(addresses)))

if __name__ == "__main__":
    main()
