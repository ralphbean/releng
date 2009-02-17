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
buildtag = 'dist-f11' # tag to build from
epoch = '2009-02-23 0:0:0.000000' # rebuild anything not built after this date
user = 'Fedora Release Engineering <rel-eng@lists.fedoraproject.org>'
comment = '- Rebuilt for https://fedoraproject.org/wiki/Fedora_11_Mass_Rebuild'
workdir = os.path.expanduser('~/massbuild')
enviro = os.environ
enviro['BUILD_FLAGS'] = '--nowait --background' # do builds with low priority
enviro['CVS_RSH'] = 'ssh' # do builds with low priority

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
        sys.stderr.write('%s failed %s: %s' % (pkg, action, e))
        return 1
    return 0


# Create a koji session
kojisession = koji.ClientSession('https://koji.fedoraproject.org/kojihub')

# Log into koji
clientcert = os.path.expanduser('~/.fedora.cert')
clientca = os.path.expanduser('~/.fedora-upload-ca.cert')
serverca = os.path.expanduser('~/.fedora-server-ca.cert')
kojisession.ssl_login(clientcert, clientca, serverca)

# Generate a list of packages to iterate over
pkgs = kojisession.listPackages(buildtag, inherited=True)

# reduce the list to those that are not blocked and sort by package name
pkgs = sorted([pkg for pkg in pkgs if not pkg['blocked'],
              key=operator.itemgetter('package_name'))

print "Checking %s packages..." % len(pkgs)

# Loop over each package
for pkg in pkgs:
    name = pkg['package_name']
    id = pkg['package_id']

    # Query to see if a build has already been attempted
    # this version requires newer koji:
    #  if  kojisession.listBuilds(id, createdAfter=epoch):
    # This version won't catch builds in flight
    if kojisession.listBuilds(id, completeAfter=epoch):
        # We've already got an attempt made, skip.
        print "Skipping %s, already attempted." % name
        continue

    # Check out cvs
    cvs = ['cvs', '-d', ':ext:jkeating@cvs.fedoraproject.org:/cvs/pkgs', 'co',
           name]
    print 'Checking out %s' % name
    if runme(cvs, 'checkout', name, enviro):
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
        sys.stderr.write('No spec found for %s' % name)
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

    # build
    build = ['make', 'build']
    print 'Building %s' % name
    runme(build, 'build', name, enviro, 
          cwd=os.path.join(workdir, name, 'devel'))