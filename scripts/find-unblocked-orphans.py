#!/usr/bin/python
#
# find-unblocked-orphans.py - A utility to find orphaned packages in pkgdb
#                             that are unblocked in koji
#
# Copyright (c) 2009 Red Hat
#
# Authors:
#     Jesse Keating <jkeating@redhat.com>
#

import koji
import fedora.client

# Set some variables
# Some of these could arguably be passed in as args.
tag = 'dist-rawhide' # tag to check in koji
develbranch = 8 # pkgdb ID for the devel branch
develorphs = [] # list of orphans on the devel branch from pkgdb

# Create a pkgdb session
pkgdb = fedora.client.PackageDB()

# Create a koji session
kojisession = koji.ClientSession('https://koji.fedoraproject.org/kojihub')

# Get a list of packages owned by orphan
pkgs = pkgdb.send_request('/users/packages/orphan',
                          req_params={'acls': ['owner'],
                                      'tg_paginate_limit': 0})

# Reduce to packages orphaned on devel
for p in pkgs.pkgs:
    for listing in p['listings']:
        if listing['collectionid'] == develbranch:
            if listing['owner'] == 9900:
                develorphs.append(p['name'])

# Get koji listings for each orphaned package
kojisession.multicall = True
for orph in develorphs:
    kojisession.listPackages(tagID=tag, pkgID=orph, inherited=True)

listings = kojisession.multiCall()

# Check the listings for unblocked packages.
for [pkg] in listings:
    if not pkg[0]['blocked']:
        print "Unblocked orphan %s" % pkg[0]['package_name']
