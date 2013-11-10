#!/usr/bin/python
#
# distcvs2distgit.py - A utility to convert Fedora's dist-cvs package repos
#                      into git repos
#
# Copyright (C) 2013 Red Hat Inc,
# SPDX-License-Identifier:	GPL-2.0
#
# Authors:
#     Jesse Keating <jkeating@redhat.com>
#

import os
import errno
import shutil
import sys
import subprocess

status = 0
modules = []
CVSROOT = '/home/fedora/jkeating/pkgs/rpms'
PARSECVS = '/home/fedora/jkeating/parsecvs.bak/parsecvs'
WORKDIR = '/home/fedora/jkeating/workdir'
OUTDIR = '/home/fedora/jkeating/repos'
BRANCHES = ['F-13', 'F-12', 'F-11', 'F-10', 'F-9', 'F-8', 'F-7', 'devel',
            'EL-6', 'EL-5', 'EL-4', 'OLPC-2', 'OLPC-3', 'FC-6']
AUTHOR = "Fedora Release Engineering <rel-eng@lists.fedoraproject.org>"

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
modules = sorted(os.listdir(CVSROOT))
#modules = ['CCfits']
print "Got %s modules" % len(modules)

curdir = os.getcwd()
# Cycle through each module and do some work
for module in modules:
    if not os.path.isdir(os.path.join(CVSROOT, module)):
        #print "Skipping %s, not a module" % module
        continue
    if os.path.isdir(os.path.join(OUTDIR, "%s.git" % module)):
        #print "Skipping already done module"
        continue
    if module == 'kernel':
        print "Skipping kernel"
    try:
        os.chdir(curdir)
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

        if os.path.exists(os.path.join(WORKDIR, module)):
            shutil.rmtree(os.path.join(WORKDIR, module))

        # Cycle through the branches to import
        for branch in branches:
            # Make our output dir
            mkdir_p(os.path.join(WORKDIR, module, branch))
            # Find all the ,v files, then stuff that output into parsecvs
            findpath = os.path.join(CVSROOT, module, branch)
            gitdir = os.path.join(WORKDIR, module, branch)
            enviro = os.environ
            enviro['GIT_DIR'] = gitdir
            findcmd = ['find', findpath, '-name', '*,v']
            findcall = subprocess.Popen(findcmd, stdout=subprocess.PIPE)
            thecmd = [PARSECVS]
            thecmd.extend(['-l', 'parsecvs.bak/edit-change-log'])

            subprocess.check_call(thecmd, env=enviro,
                                        stdin=findcall.stdout,
                                        stdout=sys.stdout,
                                        stderr=sys.stderr)

            if 'GIT_DIR' in enviro.keys():
                del enviro['GIT_DIR']

            # Now scrub some stuff out and move it around
            clonedir = os.path.join(WORKDIR, module, 'tmp')
            # Clean it out if it exists
            if os.path.exists(clonedir):
                shutil.rmtree(clonedir)
            mkdir_p(clonedir)
            clone = ['git', 'clone', '--no-hardlinks', gitdir, clonedir]
            subprocess.check_call(clone, stdout=sys.stdout, stderr=sys.stderr)
            os.chdir(clonedir)
            cmd = ['git', 'rm']
            run = False
            commit = False
            for rmfile in ('import.log', 'branch', 'Makefile'):
                if os.path.exists(rmfile):
                    run = True
                    cmd.append(rmfile)
            if run:
                subprocess.check_call(cmd, stdout=sys.stdout, stderr=sys.stderr)
                commit = True
            if os.path.exists('.cvsignore'):
                cmd = ['git', 'mv', '.cvsignore', '.gitignore']
                subprocess.check_call(cmd, stdout=sys.stdout, stderr=sys.stderr)
                commit = True
            if commit:
                cmd = ['git', 'commit', '-m', 'dist-git conversion',
                       '--author', AUTHOR]
                subprocess.check_call(cmd, stdout=sys.stdout, stderr=sys.stderr)
                cmd = ['git', 'push']
                subprocess.check_call(cmd, stdout=sys.stdout, stderr=sys.stderr)
            os.chdir(curdir)

        # Kill GIT_DIR from the environment
        if 'GIT_DIR' in enviro.keys():
            del enviro['GIT_DIR']
        # Now fetch the changes from the branch repos into the main repo
        develpath = os.path.join(WORKDIR, module, 'devel')
        for branch in branches:
            if branch == 'devel':
                continue
            gitcmd = ['git', 'fetch', os.path.join(WORKDIR, module, branch),
                      'master:%s/master' % branch.replace('-', '').lower()]
            subprocess.check_call(gitcmd, cwd=develpath, stdout=sys.stdout,
                                   stderr=subprocess.STDOUT, env=enviro)
            # get fetch stupidly sends useful stuff to stderr so we just stuff that
            # into stdout

        # Repack the repo to make it small
        gitcmd = ['git', 'repack', '-a', '-d', '-f', '--window=50', '--depth=20']
        subprocess.check_call(gitcmd, cwd=develpath, stdout=sys.stdout,
                               stderr=sys.stderr)

        # Write the module name in the description
        open(os.path.join(develpath, 'description'), 'w').write('%s\n' % module)

        # Set up the mailing list hook
        gitcmd = ['git', 'config', '--add', 'hooks.mailinglist',
                  '%s-owner@fedoraproject.org,scm-commits@lists.fedoraproject.org' % module]
        subprocess.check_call(gitcmd, cwd=develpath, stdout=sys.stdout,
                               stderr=sys.stderr)

        # Now move it into our output dir
        os.rename(develpath, os.path.join(OUTDIR, module + '.git'))


        # Now clean out the work tree
        shutil.rmtree(os.path.join(WORKDIR, module))

    except:
        print('Error with %s' % module)
        continue

print "All done!"
