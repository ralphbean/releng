#!/usr/bin/python -tt
#
# Copyright 2009, Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Authors: Will Woods <wwoods@redhat.com>
#          Seth Vidal <skvidal@fedoraproject.org>

import sys
import yum
import optparse
from rpmUtils.arch import getBaseArch

# Set some constants
critpath_groups = ['@core','@critical-path-base','@critical-path-gnome']
base_arches = ('i386', 'x86_64')
known_arches = base_arches + ('i586','i686')
fedora_baseurl = 'http://download.fedora.redhat.com/pub/fedora/linux/'
releasepath = {
    'rawhide': 'development/rawhide/$basearch/os/'
}
for r in ['12', '13', '14', '15']: # 13, 14, ...
    releasepath[r] = 'releases/%s/Fedora/$basearch/os/' % r

# Branched Fedora goes here
branched = '16'
releasepath['branched'] = 'development/%s/$basearch/os' % branched

# blacklists
blacklist = [ 'tzdata' ]

provides_cache = {}
def resolve_deps(pkg, base):
    deps = []
    for req in pkg.requires:
        if req in provides_cache:
            deps.append(provides_cache[req])
            continue
        try:
            po = base.returnPackageByDep(req)
        except yum.Errors.YumBaseError, e:
            print "ERROR: unresolved dep for %s of pkg %s" % (req[0], pkg.name)
            raise
        provides_cache[req] = po.name
        deps.append(po.name)

    return deps        

def expand_critpath(my, start_list):
    name_list = []
    # Expand the start_list to a list of names
    for name in start_list:
        if name.startswith('@'):
            print "expanding %s" % name
            count = 0
            group = my.comps.return_group(name[1:])
            for groupmem in group.mandatory_packages.keys() + group.default_packages.keys():
                if groupmem not in name_list:
                    name_list.append(groupmem)
                    count += 1
            print "%s packages added" % count
        else:
            if name not in name_list:
                name_list.append(name)
    # Iterate over the name_list
    count = 0
    pkg_list = []
    skipped_list = []
    for name in name_list:
        count += 1
        print "depsolving %4u/%4u (%s)" % (count, len(name_list), name)
        p = my.pkgSack.searchNevra(name=name)
        if not p:
            print "WARNING: unresolved package name: %s" % name
            name_list.remove(name)
            skipped_list.append(name)
            continue
        for pkg in p:
            pkg_list.append(pkg)
            for dep in resolve_deps(pkg, my):
                if dep not in name_list:
                    print "    added %s" % dep
                    name_list.append(dep)
    print "depsolving complete."
    # FIXME this isn't coming out right for i386: "-3 multiarch"?
    print "%u packages in critical path (%+i multiarch)" % (len(name_list),
                                                            len(pkg_list)-len(name_list))
    print "%u rejected package names: %s" % (len(skipped_list),
                                             " ".join(skipped_list))
    return pkg_list


def setup_yum(baseurl, arch=None, cachedir='/tmp/critpath'):
    my = yum.YumBase()
    basearch = getBaseArch()
    if arch is None:
        arch = basearch
    elif arch != basearch:
        # try to force yum to use the supplied arch rather than the host arch
        fakearch = {'i386':'i686',  'x86_64':'x86_64',  'ppc':'ppc64'}
        my.preconf.arch = fakearch[arch]
    my.conf.cachedir = cachedir
    my.conf.installroot = cachedir
    my.repos.disableRepo('*')
    my.add_enable_repo('critpath-repo-%s' % arch, baseurls=[baseurl])
    return my

def nvr(p):
    return '-'.join([p.name, p.ver, p.rel])

if __name__ == '__main__':
    # Option parsing
    releases = sorted(releasepath.keys())
    parser = optparse.OptionParser(usage="%%prog [options] [%s]" % '|'.join(releases))
    parser.add_option("--nvr", action='store_true', default=False,
                      help="output full NVR instead of just package name")
    parser.add_option("-a", "--arches", default=','.join(base_arches),
                      help="arches to evaluate (%default)")
    parser.add_option("-o", "--output", default="critpath.txt",
                      help="name of file to write critpath list (%default)")
    parser.add_option("-u", "--url", default=fedora_baseurl,
                      help="URL to repos")
    (opt, args) = parser.parse_args()
    if (len(args) != 1) or (args[0] not in releases):
        parser.error("must choose a release from the list: %s" % releases)
    (maj, min, sub) = yum.__version_info__
    if (maj < 3 or min < 2 or (maj == 3 and min == 2 and sub < 24)) and opt.arches != getBaseArch():
        print "WARNING: yum < 3.2.24 may be unable to depsolve other arches."
        print "Get a newer yum or run this on an actual %s system." % opt.arches
    f = open(opt.output,"w")
    # Sanity checking done, set some variables
    release = args[0]
    url = opt.url + releasepath[release]
    check_arches = opt.arches.split(',')

    print "Using URL %s" % url
    
    # Do the critpath expansion for each arch
    critpath = set()
    for arch in check_arches:
        print "Expanding critical path for %s" % arch
        my = setup_yum(baseurl=url, arch=arch)
        pkgs = expand_critpath(my, critpath_groups)
        print "%u packages for %s" % (len(pkgs), arch)
        if opt.nvr:
            critpath.update([nvr(p).encode('utf8') for p in pkgs])
        else:
            critpath.update([p.name.encode('utf8') for p in pkgs])
        # XXX TODO cleanup cache
        del my
        print
    # Write full list 
    for packagename in sorted(critpath):
        if packagename not in blacklist:
            f.write(packagename + "\n")
    f.close()
    print "Wrote %u items to %s" % (len(critpath), opt.output)
