#!/usr/bin/python
#
# distcvs2distgit.py - A utility to convert Fedora's dist-cvs package repos
#                      into git repos
#
# Copyright (c) 2009 Red Hat
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
#
# This program requires access to the .v files for the CVS repos to convert.
# It also requires a parsecvs binary to use, and git installed.

import os
import subprocess
import errno
import shutil

status = 0
modules = []
CVSROOT = '/home/fedora/jkeating/pkgs/rpms'
PARSECVS = '/home/fedora/jkeating/mainline/parsecvs'
WORKDIR = '/home/fedora/jkeating/workdir'
OUTDIR = '/home/fedora/jkeating/repos'
BRANCHES = ['F-12', 'F-11', 'F-10', 'F-9', 'F-8', 'F-7', 'devel', 'EL-5',
            'EL-4']

# Define some useful functions
# This was stolen from http://stackoverflow.com/questions/600268/mkdir-p-functionality-in-python
def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError, exc:
        if exc.errno == errno.EEXIST:
            pass
        else: raise

# Get a list of modules
modules = os.listdir(CVSROOT)
print "Got %s modules" % len(modules)

# Cycle through each module and do some work
for module in modules:
    if not os.path.isdir(os.path.join(CVSROOT, module)):
        print "Skipping %s, not a module" % module
        continue
    # Find branches for this build
    branches = []
    dirs = os.listdir(os.path.join(CVSROOT, module))
    for dir in dirs:
        if dir in BRANCHES:
            branches.append(dir)

    # Bail if we don't have a devel branch
    if 'devel' not in branches:
        print "Skipping %s, no devel branch" % module
        continue

    # Cycle through the branches to import
    for branch in branches:
        # Make our output dir
        mkdir_p(os.path.join(WORKDIR, module, branch))
        # open up a log file
        log = open(os.path.join(WORKDIR, module, branch, 'log'), 'w')
        # Find all the ,v files, then stuff that output into parsecvs
        findpath = os.path.join(CVSROOT, module, branch)
        gitdir = os.path.join(WORKDIR, module, branch)
        enviro = os.environ
        enviro['GIT_DIR'] = gitdir
        findcmd = ['find', findpath, '-name', '*,v']
        findcall = subprocess.Popen(findcmd, stdout=subprocess.PIPE)
        parsecvs = subprocess.Popen([PARSECVS], env=enviro,
                                    stdin=findcall.stdout)
        (output, err) = parsecvs.communicate()
        if output:
            print output
            log.write(output)
        if err:
            print "Got error parsing %s:%s" % (module, branch)
            log.write(err)
        log.close()

    # Kill GIT_DIR from the environment
    if 'GIT_DIR' in enviro.keys():
        del enviro['GIT_DIR']
    # Now fetch the changes from the branch repos into the main repo
    develpath = os.path.join(WORKDIR, module, 'devel')
    log = open(os.path.join(WORKDIR, module, 'devel', 'log'), 'a')
    for branch in branches:
        if branch == 'devel':
            continue
        gitcmd = ['git', 'fetch', os.path.join(WORKDIR, module, branch),
                  'master:%s' % branch]
        cmd = subprocess.Popen(gitcmd, cwd=develpath, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, env=enviro)
        (output, err) = cmd.communicate()
        # get fetch stupidly sends useful stuff to stderr so we just stuff that
        # into stdout
        if output:
            print output
            log.write(output)

    # Repack the repo to make it small
    gitcmd = ['git', 'repack', '-a', '-d', '-f', '--window=50', '--depth=20']
    cmd = subprocess.Popen(gitcmd, cwd=develpath, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE)
    (output, err) = cmd.communicate()
    if output:
        print output
        log.write(output)
    if err:
        print "Got error packing %s" % module
        log.write(err)
    log.close()

    # Now clone into our output dir
    gitcmd = ['git', 'clone', '--bare', develpath,
              os.path.join(OUTDIR, module + '.git')]
    cmd = subprocess.Popen(gitcmd, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE)
    (output, err) = cmd.communicate()
    if output:
        print output
    if err:
        print "Got error cloning %s.git" % module

    # Now clean out the work tree
    shutil.rmtree(os.path.join(WORKDIR, module))

print "All done!"
