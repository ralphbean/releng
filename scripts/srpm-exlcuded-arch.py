#!/usr/bin/python

# srpm-exlcuded-arch: is a tool to give you a list of packge names that
# are excluded on the given arches.  access to a srpm tree is needed.
#
# Copyright (C) 2008-2013 Red Hat, Inc.
# SPDX-License-Identifier:      GPL-2.0+
#
# Authors:
#       Dennis Gilmore <dennis@ausil.us>

import rpm
import os
import sys
import optparse
import glob

OptionParser = optparse.OptionParser
usage = "%prog [options]"
parser = OptionParser(usage=usage)
parser.add_option("-a", "--arches", 
       help="arches to check for")
parser.add_option("--path", default='./',
       help="path to dir with srpms, default current directory")
(options, args) = parser.parse_args()
arches = options.arches
if arches == None:
   print "You must pass arches to check for in."
   sys.exit()
else:
   arches = arches.split(',')

srpm_path = options.path
srpms = glob.glob('%s/*.rpm' % srpm_path)
pkglist = []

for srpm in srpms:
    """Return the rpm header."""
    ts = rpm.TransactionSet()
    ts.setVSFlags(rpm._RPMVSF_NOSIGNATURES|rpm._RPMVSF_NODIGESTS)
    fo = file(str("%s" % (srpm)), "r")
    hdr = ts.hdrFromFdno(fo.fileno())
    fo.close()
    ExcludeArch = []
    for arch in arches:
        if arch in hdr[rpm.RPMTAG_EXCLUDEARCH]:
            ExcludeArch.append(arch)
        if not hdr[rpm.RPMTAG_EXCLUSIVEARCH] == []:
            if arch not in hdr[rpm.RPMTAG_EXCLUSIVEARCH]:
                if arch not in ExcludeArch:
                    ExcludeArch.append(arch)
    if ExcludeArch == arches:
        pkgname = hdr[rpm.RPMTAG_NAME]
        if pkgname not in pkglist:
            pkglist.append(pkgname)
            #print "Excluding: %s" % pkgname

output = ""
for pkg in pkglist:
    output +=  pkg + " "

print output
