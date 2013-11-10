#!/usr/bin/python -t

# Copyright (C) 2013 Red Hat Inc.
# SPDX-License-Identifier:  GPL-2.0+

import os
import sys
import sets
import yum
import koji
import yum.Errors
from yum.misc import getCacheDir
from optparse import OptionParser
from rpmUtils.miscutils import compareEVR
import smtplib
from email.MIMEText import MIMEText
import datetime
import re
import rpmUtils.arch

if sys.hexversion < 0x020300F0:
    sys.stderr.write("%s: Sorry, Python >= 2.3 required.\n" % sys.argv[0])
    sys.exit(1)

mail_from = "buildsys@fedoraproject.org"
mail_to = "fedora-maintainers@redhat.com"
mail_subject = "Package EVR problems in FC+FE %s" % datetime.date.today()
smtp_server = None

# Add wanted distributions to "dists".  Values should be numbers (as strings),
# and all repos containing that number in their id's will be associated with
# the corresponding distro version.  For example, repo id "foo9bar" will be
# associated with distro "9".
dists = ('8', '9')

# Architectures to operate on.
archs = rpmUtils.arch.getArchList('src')

# False positive workarounds until obsoletes processing is implemented
# (not really doable as long as we operate on SRPMS): per-package tuples of
# known good paths
known_good = {
#    'koffice': (('FL3-updates', 'FE4'),
#                ('FL3-updates', 'FE5'),
#                ('FL3-updates', 'FE6'),
#                ('FL3-updates', 'FE7'),
#                ),
    }

# Where to checkout owners/owners.list
ownersworkdir = '/srv/extras-push/work'


def parseArgs():
    usage = "usage: %s [options (see -h)]" % sys.argv[0]
    parser = OptionParser(usage=usage)
    parser.add_option("-c", "--config", default='/etc/yum.conf',
                      help='config file to use (defaults to /etc/yum.conf)')
    parser.add_option("-t", "--tempcache", default=False, action="store_true",
                      help="Use a temp dir for storing/accessing yum-cache")
    parser.add_option("-d", "--cachedir", default='',
                      help="custom directory for storing/accessing yum-cache")
    parser.add_option("-q", "--quiet", default=False, action="store_true",
                      help="quiet (no output to stderr)")
    parser.add_option("-n", "--nomail", default=False, action="store_true",
                      help="do not send mail, just output the results")
    parser.add_option("-w", "--noowners", default=False, action="store_true",
                      help="do not do owners.list processing")
    parser.add_option("-x", "--nextonly", default=False, action="store_true",
                      help="check next dist version only for each package, "
                      "not all newer ones")
    parser.add_option("-m", "--missing", default=False, action="store_true",
                      help="check for packages missing in newer repos")
    (opts, args) = parser.parse_args()
    return (opts, args)

class MySolver(yum.YumBase):
    def __init__(self, arch = None, config = "/etc/yum.conf"):
        yum.YumBase.__init__(self)

        self.arch = arch
        self.doConfigSetup(fn = config)
        if hasattr(self.repos, 'sqlite'):
            self.repos.sqlite = False
            self.repos._selectSackType()

    def readMetadata(self):
        self.doRepoSetup()
        self.doSackSetup(archs)
        for repo in self.repos.listEnabled():
            self.repos.populateSack(which=[repo.id])

    def log(self, value, msg):
        pass

def evrstr(evr):
    return evr and "%s:%s-%s" % evr or "(missing)"

def koji_get_info(name, report, pkg_evr, tags=["dist-rawhide"]):
    koji_server = "http://koji.fedoraproject.org/kojihub"
    koji_session = koji.ClientSession(koji_server, {})
    fmt = "     %(nvr)-40s %(tag_name)-20s %(owner_name)s"

    for tag in tags:
        pkg = koji_session.getLatestBuilds(tag, package=name);
        if len(pkg) == 0:
            continue
        evr = ()
        e = u'0'
        if pkg[0]['epoch']:
            e = u'%s' % pkg[0]['epoch']
        v = u'%s' % pkg[0]['version']
        r = u'%s' % pkg[0]['release']
        evr = e, v, r
        if compareEVR(evr, pkg_evr) > 0:
            output = [ fmt % x for x in pkg ]
            for line in output:
                report.append(line)

def main():
    (opts, cruft) = parseArgs()

    if opts.noowners:
        owners = {}
    else:
        sys.path.append('/srv/extras-push/work/extras-repoclosure')
        from PackageOwners import PackageOwners
        owners = PackageOwners()
        #owners.FromCVS(workdir = ownersworkdir)
        if not owners.FromURL():
            sys.exit(1)

    solvers = {}

    for dist in dists:
        solver = MySolver(config = opts.config)
        for repo in solver.repos.repos.values():
            if re.sub('\D+', '', repo.id) != dist:
                repo.disable()
            else:
                repo.enable()
                solvers[dist] = solver

    if os.geteuid() != 0 or opts.tempcache or opts.cachedir != '':
        if opts.cachedir != '':
            cachedir = opts.cachedir
        else:
            cachedir = getCacheDir()
            if cachedir is None:
                print "Error: Could not make cachedir, exiting"
                sys.exit(50)

        for repo in solvers.values():
            repo.repos.setCacheDir(cachedir)

    if not opts.quiet:
        print 'Reading in repository metadata - please wait....'

    for dist in solvers.keys():
        try:
            solvers[dist].readMetadata()
        except yum.Errors.RepoError, e:
            print 'Metadata read error for dist %s, excluding it' % dist
            del solvers[dist]

    pkgdict = {}
    for dist in dists:
        pkgdict[dist] = {}

    enabled_dists = solvers.keys()
    enabled_dists.sort()

    allnames = {} # Python < 2.4 compat, otherwise we'd use sorted(set(...))
    for dist in enabled_dists:
        # Would use returnNewestByName() but it's broken in yum 3.0.1 (#220841)
        # returnNewestByNameArch() works for our purposes as long as we only
        # deal with one arch (src).
        for pkg in solvers[dist].pkgSack.returnNewestByNameArch():
            if pkg.name[-10:] == "-debuginfo": pass
            allnames[pkg.name] = 1
            pkgdict[dist][pkg.name] = {
                "evr": (pkg.epoch, pkg.version, pkg.release),
                "repo": pkg.repoid,
                }
    allnames = allnames.keys()
    allnames.sort(lambda x, y: cmp(x.lower(), y.lower()))

    report = []
    missing_report = []
    reports = {}  # report per owner, key is owner email addr

    for name in allnames:
        pkgdata = map(lambda x: pkgdict[x].get(name), enabled_dists)
        broken_paths = []

        for i in range(len(pkgdata)):
            curr = pkgdata[i]
            if not curr:
                # package missing from this dist, skip
                continue

            for next in pkgdata[i+1:]:
                if not next:
                    if opts.missing:
                        # package missing from this dist, skip
                        # TODO: warn about holes in continuum?
                        missing = "%s %s %s not in next repo" % \
                        (name, evrstr(curr["evr"]), curr["repo"])
                        missing_report.append(missing)
                        koji_get_info(name, missing_report, pkg_evr = curr["evr"])
                        missing_report.append("")
                    continue

                if compareEVR(curr["evr"], next["evr"]) > 0:
                    # candidate for brokenness
                    if not known_good.has_key(name):
                        known_good[name] = ()
                    if (curr["repo"], next["repo"]) not in known_good[name]:
                        # yep, it's broken
                        broken_paths.append((curr, next))

                if opts.nextonly:
                    break

        if broken_paths:
            if owners:
                owner = owners.GetOwner(name) or \
                        'UNKNOWN OWNER (possibly Core package)'
            else:
                owner = ''
            ownerprint = owner.replace('@',' AT ')
            if not reports.has_key(owner):
                reports[owner] = []
            reports[owner].append(name)
            report.append("%s: %s" % (name, ownerprint))
            for broken in broken_paths:
                what = "  %s > %s (%s > %s)" % \
                       (broken[0]["repo"], broken[1]["repo"],
                        evrstr(broken[0]["evr"]), evrstr(broken[1]["evr"]))
                reports[owner].append(what)
                report.append(what)
                koji_get_info(name, report, pkg_evr = broken[1]["evr"])
            reports[owner].append("")
            report.append("")

    # Insert "sorted by owner" report at the top.
    oldreport = report
    report = []
    if not opts.noowners:
        reportkeys = reports.keys()
        reportkeys.sort()
        for owner in reportkeys:
            ownerprint = owner.replace('@',' AT ')
            report.append(ownerprint+':')
            for line in reports[owner]:
                report.append('    '+line)
    if report:
        report.append('-'*70)
        report.append('')
    report += oldreport

    report = "\n".join(report)
    if report:
        if mail_to and not opts.nomail:
            msg = MIMEText(report)
            msg["Subject"] = mail_subject
            msg["From"] = mail_from
            msg["To"] = mail_to
            s = smtplib.SMTP()
            if smtp_server:
                s.connect(smtp_server)
            else:
                s.connect()
            s.sendmail(mail_from, [mail_to], msg.as_string())
            s.close()
        else:
            print report

    if missing_report:
        for line in missing_report:
            print line

if __name__ == "__main__":
    main()

# Local variables:
# indent-tabs-mode: nil
# py-indent-offset: 4
# End:
# ex: ts=4 sw=4 et
