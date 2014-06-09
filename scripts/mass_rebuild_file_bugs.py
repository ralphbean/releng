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
import tempfile
import urllib2
from bugzilla.rhbugzilla import RHBugzilla
from xmlrpclib import Fault
from find_failures import get_failed_builds

# Set some variables
# Some of these could arguably be passed in as args.
buildtag = 'f21-rebuild' # tag to check
desttag = 'f21' # Tag where fixed builds go
epoch = '2014-06-06 00:00:00.000000' # rebuild anything not built after this date
failures = {} # dict of owners to lists of packages that failed.
failed = [] # raw list of failed packages

product = "Fedora" # for BZ product field
version = "rawhide" # for BZ version field
tracking_bug = 1105908 # Tracking bug for mass build failures


def report_failure(product, component, version, summary, comment, logs):
    """This function files a new bugzilla bug for component with given
    arguments

    Keyword arguments:
    product -- bugzilla product (usually Fedora)
    component -- component (package) to file bug against
    version -- component version to file bug for (usually rawhide for Fedora)
    summary -- short bug summary
    comment -- first comment describing the bug in more detail
    logs -- list of the log file to attach to the bug report

    """
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
        print 'Creating the bug report'
        bug = bzclient.createbug(**data)
        #print "Running bzcreate: %s" % data
        bug.refresh()
        print bug
        for log in logs:
            name = log.rsplit('/', 1)[-1]
            response = urllib2.urlopen(log)
            fp = tempfile.TemporaryFile()
            fp.write(response.read())
            fp.seek(0)
            try:
                print 'Attaching file %s to the ticket' % name
                attid = bzclient.attachfile(
                    bug.id, fp, name, content_type='text/plain')
            except Fault, ex:
                print ex
            finally:
                fp.close()
    except Fault, ex:
        print ex
        username = raw_input('Bugzilla username: ')
        bzclient.login(user=username,
                       password=getpass.getpass())
        report_failure(product, component, version, summary, comment, logs)


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


def get_task_failed(kojisession, task_id):
    ''' For a given task_id, use the provided kojisession to return the
    task_id of the first children that failed to build.
    '''
    for child in kojisession.getTaskChildren(task_id):
        if child['state'] == 5:  # 5 == Failed
            return child['id']


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

        child_id = get_task_failed(kojisession, task_id)
        if not child_id:
            print 'No children failed for task: %s (%s)' % (
                task_id, component)
            logs = []
        else:
            base_path = koji.pathinfo.taskrelpath(child_id)
            log_url = "%s/%s/" % (work_url, base_path)
            build_log = log_url + "build.log"
            root_log = log_url + "root.log"
            state_log = log_url + "state.log"
            logs = [build_log, root_log, state_log]

        comment = """Your package %s failed to build from source in current rawhide.

http://koji.fedoraproject.org/koji/taskinfo?taskID=%s

For details on mass rebuild see https://fedoraproject.org/wiki/Fedora_21_Mass_Rebuild
""" % (component, task_id)

        if component not in filed_bugs_components:
            print "Filing bug for %s" % component
            report_failure(
                product, component, version, summary, comment, logs=logs)
            filed_bugs_components.append(component)
        else:
            print "Skipping %s, bug already filed" % component
