#!/usr/bin/python
#
# mass_rebuild_file_bugs.py - A utility to discover failed builds in a
#    given tag and file bugs in bugzilla for these failed builds
#
# Copyright (C) 2013 Red Hat, Inc.
# SPDX-License-Identifier:      GPL-2.0+
#
# Authors:
#     Stanislav Ochotnicky <sochotnicky@redhat.com>
#

import koji
import getpass
from bugzilla.rhbugzilla import RHBugzilla
from xmlrpclib import Fault
from find_failures import get_failed_builds

# Set some variables
# Some of these could arguably be passed in as args.
buildtag = 'f20-rebuild' # tag to check
desttag = 'f20' # Tag where fixed builds go
epoch = '2013-07-25 00:00:00.000000' # Date to check for failures from
failures = {} # dict of owners to lists of packages that failed.
failed = [] # raw list of failed packages

product = "Fedora" # for BZ product field
version = "rawhide" # for BZ version field
tracking_bug = 991858 # Tracking bug for mass build failures

def report_failure(product, component, version, summary, comment):
    """This function files a new bugzilla bug for component with given arguments

    Keyword arguments:
    product -- bugzilla product (usually Fedora)
    component -- component (package) to file bug against
    version -- component version to file bug for (usually rawhide for Fedora)
    summary -- short bug summary
    comment -- first comment describing the bug in more detail"""
    data = {
        'product': product,
        'component': component,
        'version': version,
        'short_desc': summary,
        'comment': comment,
        'blocks': tracking_bug,
        'rep_platform': 'Unspecified',
        'bug_severity': 'unspecified',
        'op_sys': 'Unspecified',
        'bug_file_loc': '',
        'priority': 'unspecified',
        }
    bzurl = 'https://bugzilla.redhat.com'
    bzclient = RHBugzilla(url="%s/xmlrpc.cgi" % bzurl)
    try:
        bug = bzclient.createbug(**data)
        print "Running bzcreate: %s" % data
        bug.refresh()
    except Fault, ex:
        print ex
        username = raw_input('Bugzilla username: ')
        bzclient.login(user=username,
                       password=getpass.getpass())
        report_failure(component, summary, comment)

def get_filed_bugs(tracking_bug):
    """Query bugzilla if given bug has already been filed

    Keyword arguments:
    product -- bugzilla product (usually Fedora)
    component -- component (package) to file bug against
    version -- component version to file bug for (usually rawhide for Fedora)
    summary -- short bug summary
    """
    query_data = {'blocks': tracking_bug}
    bzurl = 'https://bugzilla.redhat.com'
    bzclient = RHBugzilla(url="%s/xmlrpc.cgi" % bzurl)

    return bzclient.query(query_data)


if __name__ == '__main__':
    kojisession = koji.ClientSession('http://koji.fedoraproject.org/kojihub')
    print 'Getting the list of failed builds...'
    failbuilds = get_failed_builds(kojisession, epoch, buildtag, desttag)
    print 'Getting the list of filed bugs...'
    filed_bugs = get_filed_bugs(tracking_bug)
    filed_bugs_components = [bug.component for bug in filed_bugs]
    for build in failbuilds:
        global product, version
        task_id = build['task_id']
        component = build['package_name']
        summary = "%s: FTBFS in %s" % (component, 'rawhide')
        work_url = 'http://kojipkgs.fedoraproject.org/work'
        base_path = koji.pathinfo.taskrelpath(task_id)
        log_url = "%s/%s/" % (work_url, base_path)
        build_log = log_url + "build.log"
        root_log = log_url + "root.log"
        state_log = log_url + "state.log"
        comment = """Your package %s failed to build from source in current rawhide.

http://koji.fedoraproject.org/koji/taskinfo?taskID=%s

For details on mass rebuild see https://fedoraproject.org/wiki/Fedora_20_Mass_Rebuild
""" % (component, task_id)

        if component not in filed_bugs_components:
            print "Filing bug for %s" % component
            report_failure(product, component, version, summary, comment)
            filed_bugs_components.append(component)
        else:
            print "Skipping %s, bug already filed" % component
