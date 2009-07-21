#!/usr/bin/python
#
# find-unblocked-orphans.py - A utility to find orphaned packages in pkgdb
#                             that are unblocked in koji and to show what
#                             may require those orphans
#
# Copyright (c) 2009 Red Hat
#
# Authors:
#     Jesse Keating <jkeating@redhat.com>
#

import koji
import fedora.client
import yum
import os
import sys
import tempfile
import shutil

# Set some variables
# Some of these could arguably be passed in as args.
repo = 'http://kojipkgs.fedoraproject.org/mash/rawhide/i386/os'
srepourl = 'http://kojipkgs.fedoraproject.org/mash/rawhide/source/SRPMS'
tag = 'dist-rawhide' # tag to check in koji
develbranch = 8 # pkgdb ID for the devel branch
orphanuid = 'orphan' # pkgdb uid for orphan
develorphs = [] # list of orphans on the devel branch from pkgdb
unblocked = {} # holding dict for unblocked orphans plus their deps

# Create a pkgdb session
pkgdb = fedora.client.PackageDB()

# Create a koji session
kojisession = koji.ClientSession('https://koji.fedoraproject.org/kojihub')

# Get a list of packages owned by orphan
pkgs = pkgdb.send_request('/packages/orphans',
                          req_params={'tg_paginate_limit': 0})

# Reduce to packages orphaned on devel
for p in pkgs.pkgs:
    for listing in p['listings']:
        if listing['collectionid'] == develbranch:
            if listing['owner'] == orphanuid:
                develorphs.append(p['name'])

# Get koji listings for each orphaned package
kojisession.multicall = True
for orph in develorphs:
    kojisession.listPackages(tagID=tag, pkgID=orph, inherited=True)

listings = kojisession.multiCall()

# Check the listings for unblocked packages.
for [pkg] in listings:
    if not pkg[0]['blocked']:
        unblocked[pkg[0]['package_name']] = {}
        print "Unblocked orphan %s" % pkg[0]['package_name']

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
            for pkg in yb.pkgSack.searchRequires(prov.split()[0]):
                if pkg in bin_by_src[orph]:
                    continue
                # use setdefault to either create an entry for the
                # required package or append what provides it needs
                unblocked[orph].setdefault(pkg.name, []).append(prov)
    except KeyError:
        pass # If we don't have a package in the repo, there is nothign to do

print "\nList of deps left behind by orphan removal:"
for orph in sorted(unblocked.keys()):
    if unblocked[orph]:
        print "\nOrphan: %s" % orph
    for dep in sorted(unblocked[orph].keys()):
        # Use a set here to quash duplicate requires
        for req in set(unblocked[orph][dep]):
            print "    %s requires %s" % (dep, req)

# Clean up our tempdir
shutil.rmtree(tempdir)
