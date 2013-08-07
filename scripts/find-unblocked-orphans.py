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

import koji
import fedora.client
import yum
import os
import sys
import tempfile
import shutil

# Set some variables
# Some of these could arguably be passed in as args.
# If this is pre-branch, these repos should be rawhide; otherwise,
# they should be branched.
repo = 'http://kojipkgs.fedoraproject.org/mash/rawhide/i386/os'
srepourl = 'http://kojipkgs.fedoraproject.org/mash/rawhide/source/SRPMS'
tag = 'f20' # tag to check in koji

# pre-branch, this should be 8 and 'devel'. Post-branch, you need
# to look it up via:
#  pkgdb = fedora.client.PackageDB()
#  list = pkgdb.get_collection_list()
# Will generally be 20-something and 'F-xx'
develbranch = 8 # pkgdb ID for the devel branch
develbranchname = 'devel' # pkgdb name for the devel branch

orphanuid = 'orphan' # pkgdb uid for orphan
orphans = {} # list of orphans on the devel branch from pkgdb
unblocked = {} # holding dict for unblocked orphans plus their deps

def _comaintainers(package):
    comaint = []
    pkginfo = pkgdb.get_package_info(package, branch = develbranchname)
    users = pkginfo.packageListings[0]['people']
    for user in users:
        acl = user['aclOrder']
        if acl['commit'] or acl['approveacls']:
            comaint.append(user['username'])
    return comaint

# Create a pkgdb session
pkgdb = fedora.client.PackageDB()

# Create a koji session
kojisession = koji.ClientSession('https://koji.fedoraproject.org/kojihub')

sys.stderr.write('Contacting pkgdb for list of orphans...\n')
# Get a list of packages owned by orphan
pkgs = pkgdb.send_request('/acls/orphans',
                          req_params={'pkgs_tgp_limit': 0})

sys.stderr.write('Getting comaintainers...\n')
# Reduce to packages orphaned on devel
for p in pkgs.pkgs:
    for listing in p['listings']:
        if listing['collectionid'] == develbranch:
            # statuscode cheatsheet:
            # 14 orphaned
            # 20 deprecated
            if listing['owner'] == orphanuid and listing['statuscode'] == 14:
                orphans[p['name']] = { 'name': p['name'], 'comaintainers' : _comaintainers(p['name']) }

failed = {}
for pkg in sys.argv[1:]:
    failed[pkg] = { 'name': pkg, 'comaintainers' : _comaintainers(pkg) }

sys.stderr.write('Getting builds from koji...\n')
# Get koji listings for each orphaned package
kojisession.multicall = True

orphanlist = orphans.keys() + failed.keys()
orphanlist.sort()
for orph in orphanlist:
    kojisession.listPackages(tagID=tag, pkgID=orph, inherited=True)

listings = kojisession.multiCall()

# Check the listings for unblocked packages.
for [pkg] in listings:
    if not pkg[0]['blocked']:
        unblocked[pkg[0]['package_name']] = {}
        if pkg[0]['package_name'] in orphans.keys():
            print "Package %s (orphan)" % pkg[0]['package_name']
            if orphans[pkg[0]['package_name']]['comaintainers']:
                print "\tcomaintained by: %s" % (' '.join(orphans[pkg[0]['package_name']]['comaintainers']),)
        else:
            print "Package %s (fails to build)" % pkg[0]['package_name']
            if failed[pkg[0]['package_name']]['comaintainers']:
                print "\tcomaintained by: %s" % (' '.join(failed[pkg[0]['package_name']]['comaintainers']),)

sys.stderr.write('Calculating dependencies...\n')
# This code was mostly stolen from
# http://yum.baseurl.org/wiki/YumCodeSnippet/SetupArbitraryRepo
# Create yum object and depsolve out if requested.
# TODO: add app args to either depsolve or not
yb = yum.YumBase()
yb.preconf.init_plugins=False
tempdir = tempfile.mkdtemp(dir='/tmp/')
yb.conf.basecachedir = tempdir
if not os.path.exists(yb.conf.basecachedir):
    os.makedirs(yb.conf.basecachedir)
yb.conf.cache = 0

yb.repos.disableRepo('*')
newrepo = yum.yumRepo.YumRepository('myrepo')
newrepo.name = 'myrepo - %s' % repo
newrepo.baseurl = [repo]
newrepo.basecachedir = yb.conf.basecachedir
newrepo.enablegroups = True
srepo = yum.yumRepo.YumRepository('mysrepo')
srepo.name = 'mysrepo - %s' % srepourl
srepo.baseurl = [srepourl]
srepo.basecachedir = yb.conf.basecachedir
srepo.enablegroups = True
yb.repos.add(newrepo)
yb.repos.add(srepo)
yb.repos.enableRepo(newrepo.id)
yb.repos.enableRepo(srepo.id)
yb.doRepoSetup(thisrepo=newrepo.id)
yb.doRepoSetup(thisrepo=srepo.id)

# Manually setup the arch list and add src, then manually populate the sack
# In f12 rawhide you can just do yb.arch.archlist.append('src') and skip
# manual population of the sack
archs = yum.rpmUtils.arch.getArchList(thisarch='i686') + ['src']
yb._getSacks(archlist=archs)

# This function was stolen from pungi
def getSRPMPo(po):
    """Given a package object, get a package object for the
       corresponding source rpm. Requires yum still configured
       and a valid package object."""
    srpm = po.sourcerpm.split('.src.rpm')[0]
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

src_by_bin = {} # Dict of source pkg objects by binary package objects
bin_by_src = {} # Dict of binary pkgobjects by srpm name
(dummy1, everything, dummy2) = yum.packages.parsePackages(
                               yb.pkgSack.returnPackages(), ['*'])
# Populate the dicts
for po in everything:
    if po.arch == 'src':
        continue
    srpmpo = getSRPMPo(po)
    src_by_bin[po] = srpmpo
    if bin_by_src.has_key(srpmpo.name):
        bin_by_src[srpmpo.name].append(po)
    else:
        bin_by_src[srpmpo.name] = [po]

allorphaned = []
for orph in unblocked.keys():
    try:
        for pkg in bin_by_src[orph]:
            allorphaned.append(pkg.name)
    except:
        # Package is for another arch
        pass

# Generate a dict of orphans to things requiring them and why
# Some of this code was stolen from repoquery
for orph in unblocked.keys():
    provs = []
    try: # We may have some orphans that aren't in the repo
        for pkg in bin_by_src[orph]:
            # add all the provides from the package as strings
            provs.extend([yum.misc.prco_tuple_to_string(prov)
                          for prov in pkg.provides])
            # add all the files, removing spurious //
            for ftype in pkg.files.keys():
                provs.extend([os.path.normpath('//%s' % fn)
                              for fn in pkg.files[ftype]])

        # Zip through the provs and find what's needed
        # We only care about the base provide, not the specific versions
        for prov in provs:
            skip = 0
            # Elide other providers
            for pkg in yb.pkgSack.searchProvides(prov.split()[0]):
                if pkg.name not in allorphaned:
                    skip = 1
            if skip == 1:
                continue
            for pkg in yb.pkgSack.searchRequires(prov.split()[0]):
                if pkg in bin_by_src[orph]:
                    continue
                if pkg.name in allorphaned:
                    continue
                # use setdefault to either create an entry for the
                # required package or append what provides it needs
                unblocked[orph].setdefault(pkg.name, []).append(prov)
    except KeyError:
        sys.stderr.write("Orphaned package %s doesn't appear to exist\n" % (orph,))
        pass # If we don't have a package in the repo, there is nothign to do

print "\nList of deps left behind by packages which are orphaned or fail to build:"
for orph in sorted(unblocked.keys()):
    if unblocked[orph]:
        print "\nRemoving: %s" % orph
    for dep in sorted(unblocked[orph].keys()):
        # Use a set here to quash duplicate requires
        for req in set(unblocked[orph][dep]):
            print "    %s requires %s" % (dep, req)

# Clean up our tempdir
shutil.rmtree(tempdir)

# Print a blurb about where the code came from
print '\nThe script creating this output is run and developed by Fedora'
print 'Release Engineering. Please report issues at its trac instance:'
print 'https://fedorahosted.org/rel-eng/'
print 'The sources of this script can be found at:'
print 'https://git.fedorahosted.org/cgit/releng/tree/scripts/find-unblocked-orphans.py'
