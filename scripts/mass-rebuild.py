#!/usr/bin/python
#
# mass-rebuild.py - A utility to rebuild packages.
#
# Copyright (c) 2009 Red Hat
#
# Authors:
#     Jesse Keating <jkeating@redhat.com>
#

import koji
import os
import subprocess
import sys
import operator

# Set some variables
# Some of these could arguably be passed in as args.
buildtag = 'dist-f12' # tag to build from
epoch = '2009-07-24 08:06:00.000000' # rebuild anything not built after this date
user = 'Fedora Release Engineering <rel-eng@lists.fedoraproject.org>'
comment = '- Rebuilt for https://fedoraproject.org/wiki/Fedora_12_Mass_Rebuild'
workdir = os.path.expanduser('~/massbuild')
enviro = os.environ
target = 'dist-f12-rebuild'
enviro['CVS_RSH'] = 'ssh' # use ssh for cvs

# Define functions

# This function needs a dry-run like option
def runme(cmd, action, pkg, env, cwd=workdir):
    """Simple function to run a command and return 0 for success, 1 for
       failure.  cmd is a list of the command and arguments, action is a
       name for the action (for logging), pkg is the name of the package
       being operated on, env is the environment dict, and cwd is where
       the script should be executed from."""

    try:
        subprocess.check_call(cmd, env=env, cwd=cwd)
    except subprocess.CalledProcessError, e:
        sys.stderr.write('%s failed %s: %s\n' % (pkg, action, e))
        return 1
    return 0

# This function needs a dry-run like option
def runmeoutput(cmd, action, pkg, env, cwd=workdir):
    """Simple function to run a command and return output if successful. 
       cmd is a list of the command and arguments, action is a
       name for the action (for logging), pkg is the name of the package
       being operated on, env is the environment dict, and cwd is where
       the script should be executed from.  Returns 0 for failure"""

    try:
        pid = subprocess.Popen(cmd, env=env, cwd=cwd,
                               stdout=subprocess.PIPE)
    except BaseException, e:
        sys.stderr.write('%s failed %s: %s\n' % (pkg, action, e))
        return 0
    result = pid.communicate()[0].rstrip('\n')
    return result


# Create a koji session
kojisession = koji.ClientSession('https://koji.fedoraproject.org/kojihub')

# Generate a list of packages to iterate over
pkgs = kojisession.listPackages(buildtag, inherited=True)

# reduce the list to those that are not blocked and sort by package name
pkgs = sorted([pkg for pkg in pkgs if not pkg['blocked']],
              key=operator.itemgetter('package_name'))

print 'Checking %s packages...' % len(pkgs)

# Loop over each package
for pkg in pkgs:
    name = pkg['package_name']
    id = pkg['package_id']

    # Query to see if a build has already been attempted
    # this version requires newer koji:
    builds = kojisession.listBuilds(id, createdAfter=epoch)
    newbuild = False
    # Check the builds to make sure they were for the target we care about
    for build in builds:
        buildtarget = kojisession.getTaskInfo(build['task_id'],
                                   request=True)['request'][1]
        if buildtarget == target or buildtarget == buildtag:
            # We've already got an attempt made, skip.
            newbuild = True
            break
    if newbuild:
        print 'Skipping %s, already attempted.' % name
        continue

    # Check out cvs
    cvs = ['cvs', '-d', ':ext:jkeating@cvs.fedoraproject.org:/cvs/pkgs', 'co',
           name]
    print 'Checking out %s' % name
    if runme(cvs, 'checkout', name, enviro):
        continue

    # Check for a devel branch
    if not os.path.exists(os.path.join(workdir, name, 'devel')):
        sys.stderr.write('%s failed devel branch check.\n' % name)
        continue

    # Check for a noautobuild file
    if os.path.exists(os.path.join(workdir, name, 'devel', 'noautobuild')):
        # Maintainer does not want us to auto build.
        print 'Skipping %s due to opt-out' % name
        continue

    # Find the spec file
    files = os.listdir(os.path.join(workdir, name, 'devel'))
    spec = ''
    for file in files:
        if file.endswith('.spec'):
            spec = os.path.join(workdir, name, 'devel', file)
            break

    if not spec:
        sys.stderr.write('%s failed spec check\n' % name)
        continue

    # rpmdev-bumpspec
    bumpspec = ['rpmdev-bumpspec', '-u', user, '-c', comment,
                os.path.join(workdir, name, 'devel', spec)]
    print 'Bumping %s' % spec
    if runme(bumpspec, 'bumpspec', name, enviro):
        continue

    # cvs commit
    commit = ['cvs', 'commit', '-m', comment]
    print 'Committing changes for %s' % name
    if runme(commit, 'commit', name, enviro,
                 cwd=os.path.join(workdir, name, 'devel')):
        continue

    # cvs tag
    tag = ['make', 'tag']
    print 'Tagging %s' % name
    if runme(tag, 'tag', name, enviro,
                 cwd=os.path.join(workdir, name, 'devel')):
        continue

    # get cvs url
    urlcmd = ['make', 'cvsurl']
    print 'Getting cvs url for %s' % name
    url = runmeoutput(urlcmd, 'cvsurl', name, enviro,
                 cwd=os.path.join(workdir, name, 'devel'))
    if not url:
        continue

    # build
    build = ['koji', 'build', '--nowait', '--background', target, url]
    print 'Building %s' % name
    runme(build, 'build', name, enviro, 
          cwd=os.path.join(workdir, name, 'devel'))
