#!/usr/bin/python

# Copyright (C) 2013 Red Hat Inc,
# SPDX-License-Identifier:	GPL-2.0+

import sys
import koji
import pprint
import rpm
import re
import xmlrpclib
from optparse import OptionParser

def _(args):
    """Stub function for translation"""
    return args

def ensure_connection(session):
    try:
        ret = session.getAPIVersion()
    except xmlrpclib.ProtocolError:
        error(_("Error: Unable to connect to server"))
    if ret != koji.API_VERSION:
        print _("WARNING: The server is at API version %d and the client is at %d" % (ret, koji.API_VERSION))
    return True

def error(msg=None, code=1):
    if msg:
        sys.stderr.write(msg + "\n")
        sys.stderr.flush()
    sys.exit(code)

def compare_pkgs(pkg1, pkg2):
    """Helper function to compare two package versions
         return 1 if a > b
         return 0 if a == b
         return -1 if a < b"""
    # the 'or 0' is because some epoch's that should be 0 but are None
    # and in rpm.labelCompare(), None < 0
    e1 = str(pkg1['epoch'] or 0)
    v1 = str(pkg1['version'])
    r1 = str(pkg1['release'])
    e2 = str(pkg2['epoch'] or 0)
    v2 = str(pkg2['version'])
    r2 = str(pkg2['release'])
    #print "(%s, %s, %s) vs (%s, %s, %s)" % (e1, v1, r1, e2, v2, r2)
    return rpm.labelCompare((e1, v1, r1), (e2, v2, r2))

def diff_changelogs(session, pkg1, pkg2):
    cl2 = session.getChangelogEntries(pkg2['build_id'])
    for x in session.getChangelogEntries(pkg1['build_id']):
        try:
            cl2.remove(x)
        except ValueError:
            pass
    return cl2
    #return session.getChangelogEntries(pkg2['build_id'], after=pkg1['completion_time'])

def print_hidden_packages(session, tag, opts, pkg_list=None):
    """Find and print the "hidden" packages of the given tag"""

    # get inheritance data from the server
    if opts['parent']:
        comp_tags = [session.getTag(opts['parent'])]
        if not comp_tags[0]:
            print "Parent tag unknown, ignoring --parent"
            comp_tags = session.getFullInheritance(tag['id'], None, opts['reverse'], opts['stop'], opts['jump'])
        else:
            # makes the parent tag look more like data returned from getFullInheritance()
            comp_tags[0].update({'parent_id': comp_tags[0]['id']})
    else:
        comp_tags = session.getFullInheritance(tag['id'], None, opts['reverse'], opts['stop'], opts['jump'])

    # Key names when getting inheritace can be werid.  When doing
    # an inheritance search, 'parent_id' is the id of the tag we
    # want, but when we do --reverse, it needs to be 'id' instead.
    if opts['reverse']:
        ctag_id_key = 'tag_id'
    else:
        ctag_id_key = 'parent_id'

    if opts['verbose']:
        print "\nComparing %s (%d) to the following tags:" % (tag['name'], tag['id'])
        for ct in comp_tags:
            try:
                print "%s%s (%d)" % (" "*ct.get('currdepth',0), ct['name'], ct[ctag_id_key])
            except KeyError:
                pass

    if opts['verbose']:
        print "\nBuilding package lists:"

    # Build {package_name: pkg} list for all our tags
    main_latest = {}    #latest by nvr
    main_top = {}       #latest by tag ordering
    if opts['verbose']:
        print "%s ..." % tag['name']
    tagged_pkgs = session.listTagged(tag['id'], latest=True)
    if opts['verbose']:
        print " [%d packages]" % len(tagged_pkgs)
    for pkg in tagged_pkgs:
        if pkg_list and not pkg['package_name'] in pkg_list:
            continue
        main_top.setdefault(pkg['package_name'], pkg)
        if main_latest.has_key(pkg['package_name']) and (compare_pkgs(pkg, main_latest[pkg['package_name']]) == -1):
            continue
        main_latest[pkg['package_name']] = pkg

    comp_latest = {}    #latest by nvr
    comp_top = {}       #latest by tag ordering
    for ctag in comp_tags:
        if opts['verbose']:
            print "%s ..." % ctag['name']
        tagged_pkgs = session.listTagged(ctag[ctag_id_key], latest=True)
        if opts['verbose']:
            print " [%d packages]" % len(tagged_pkgs)
        comp_latest[ctag['name']] = {}
        comp_top[ctag['name']] = {}
        for pkg in tagged_pkgs:
            if pkg_list and not pkg['package_name'] in pkg_list:
                continue
            comp_top[ctag['name']].setdefault(pkg['package_name'], pkg)
            if comp_latest[ctag['name']].has_key(pkg['package_name']) and (compare_pkgs(pkg, comp_latest[ctag['name']][pkg['package_name']]) == -1):
                continue
            comp_latest[ctag['name']][pkg['package_name']] = pkg

    # Check for invalid packages
    if pkg_list and opts['verbose']:
        for pkg in pkg_list:
            if not pkg in main_latest:
                print "%s is not a valid package in tag %s" % (pkg, tag['name'])
            for ctag in comp_latest.keys():
                if not pkg in comp_latest[ctag]:
                    print "%s is not a valid package in tag %s" % (pkg, ctag)

    if main_latest:
        keys = main_latest.keys()
        keys.sort()
        if not opts['tag_order']:
            if opts['verbose']:
                print "\nComparing packages within %s:" % tag['name']
            for pkg in keys:
                #compare latest by tag order to latest by nvr (within original tag)
                if opts['debug']:
                    print "comparing %s to %s (%s)" % (main_latest[pkg], main_top[pkg], tag['name'])
                if opts['reverse']:
                    if (compare_pkgs(main_top[pkg], main_latest[pkg]) == 1):
                        print "%s < %s (%s)" % (main_latest[pkg]['nvr'], main_top[pkg]['nvr'], tag['name'])
                else:
                    if (compare_pkgs(main_top[pkg], main_latest[pkg]) == -1):
                        print "%s > %s (%s)" % (main_latest[pkg]['nvr'], main_top[pkg]['nvr'], tag['name'])
                        if opts['changelogs']:
                            for cl in diff_changelogs(session, main_top[pkg], main_latest[pkg]):
                                print "%(date)s - %(author)s\n%(text)s\n" % cl
        if opts['verbose']:
            print "\nComparing Packages:"
        if opts['tag_order']:
            main_latest = main_top
            comp_latest = comp_top
        for pkg in keys:
            for ctag in comp_latest.keys():
                if comp_latest[ctag].has_key(pkg):
                    if opts['debug']:
                        print "comparing %s (%s) to %s (%s)" % (comp_latest[ctag][pkg]['nvr'], ctag, main_latest[pkg]['nvr'], tag['name'])
                    if opts['reverse']:
                        if (compare_pkgs(main_latest[pkg], comp_latest[ctag][pkg]) == 1):
                            print "%s (%s) < %s (%s)" % (comp_latest[ctag][pkg]['nvr'], ctag, main_latest[pkg]['nvr'], tag['name'])
                    else:
                        if (compare_pkgs(main_latest[pkg], comp_latest[ctag][pkg]) == -1):
                            print "%s (%s) > %s (%s)" % (comp_latest[ctag][pkg]['nvr'], ctag, main_latest[pkg]['nvr'], tag['name'])
                            if opts['changelogs']:
                                for cl in diff_changelogs(session, main_latest[pkg], comp_latest[ctag][pkg]):
                                    print "%(date)s - %(author)s\n%(text)s\n" % cl

    else:
        if opts['verbose']:
            print "Oops, no packages to compare in the main tag (%s)" % tag['name']

if __name__ == "__main__":
    usage = _("Usage: find-hidden-packages [options] tag <pkg> [<pkg>...]")
    #usage += _("\n(Specify the --help global option for a list of other help options)")
    parser = OptionParser(usage=usage)
    parser.disable_interspersed_args()
    parser.add_option("-v", "--verbose", action="store_true", help=_("Be verbose"))
    parser.add_option("-d", "--debug", action="store_true", default=False,
                      help=_("Show debugging output"))
    parser.add_option("-s", "--server", default="http://koji.fedoraproject.org/kojihub",
                      help=_("Url of koji XMLRPC server"))
    parser.add_option("-p", "--parent", help=_("Compare against a single parent"))
    parser.add_option("--reverse", action="store_true", help=_("Process tag's children instead of its parents"))
    parser.add_option("--changelogs", action="store_true", help=_("Print the differing changelog entries"))
    parser.add_option("--tag-order", action="store_true", help=_("Use tag ordering within tags"))
    parser.add_option("--stop", help=_("Stop processing inheritance at this tag"))
    parser.add_option("--jump", help=_("Jump from one tag to another when processing inheritance"))

    (options, args) = parser.parse_args()

    # parse arguments
    opts = {}
    opts['debug'] = options.debug
    opts['verbose'] = options.verbose or options.debug
    opts['parent'] = options.parent
    opts['reverse'] = options.reverse or False
    opts['changelogs'] = options.changelogs or False
    opts['stop'] = {}
    opts['jump'] = {}
    opts['tag_order'] = options.tag_order

    if opts['parent'] and opts['reverse']:
        error("Cannot specify both --parent and --reverse")

    # setup server connection
    session_opts = {'debug': opts['debug']}
    kojihub = koji.ClientSession(options.server,session_opts)

    # just quick sanity check on the args before we connect to the server
    if len(args) < 1:
        error("You must specify a tag")

    try:
        # make sure we can connect to the server
        ensure_connection(kojihub)
        if options.debug:
            print "Successfully connected to hub"
    except (KeyboardInterrupt,SystemExit):
        pass
    except:
        if options.debug:
            raise
        else:
            exctype, value = sys.exc_info()[:2]
            rv = 1
            print "%s: %s" % (exctype, value)

    # validate the tag
    tag = kojihub.getTag(args[0])
    if not tag:
        parser.error(_("Unknown tag: %s" % args[0]))

    # parse jump option
    if options.jump:
        match = re.match(r'^(.*)/(.*)$', options.jump)
        if match:
            tag1 = kojihub.getTagID(match.group(1))
            if not tag1:
                parser.error(_("Unknown tag: %s" % match.group(1)))
            tag2 = kojihub.getTagID(match.group(2))
            if not tag2:
                parser.error(_("Unknown tag: %s" % match.group(2)))
            opts['jump'][str(tag1)] = tag2

    # parse stop option
    if options.stop:
        tag1 = kojihub.getTagID(options.stop)
        if not tag1:
            parser.error(_("Unknown tag: %s" % options.stop))
        opts['stop'] = {str(tag1): 1}

    # check for specific packages
    pkgs = None
    if len(args) > 1:
        pkgs = args[1:]

    rv = 0
    try:
        rv = print_hidden_packages(kojihub, tag, opts, pkgs)
    except (KeyboardInterrupt,SystemExit):
        pass
    sys.exit(rv)
