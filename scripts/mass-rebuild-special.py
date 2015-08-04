#!/usr/bin/python
#
# mass-rebuild.py - A utility to rebuild packages.
#
# Copyright (C) 2009-2013 Red Hat, Inc.
# SPDX-License-Identifier:      GPL-2.0+
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
buildtag = 'f24' # tag to build from
secondbuildtag = 'f23' # tag to build from
targets = ['f23-candidate', 'rawhide', 'f23'] # tag to build from
epoch = '2014-06-14 14:30:00.000000' # rebuild anything not built after this date
user = 'Fedora Release Engineering <rel-eng@lists.fedoraproject.org>'
comment = '- Rebuilt for https://fedoraproject.org/wiki/Changes/F23Boost159'
workdir = os.path.expanduser('~/massbuild-boost')
enviro = os.environ
targets = ['f24-boost','f23-boost']
branches = ['master', 'f23']
enviro['CVS_RSH'] = 'ssh' # use ssh for cvs

pkg_skip_list = ['shim', 'shim-signed', 'kernel', 'grub2', 'gcc', 'glibc']

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
kojisession = koji.ClientSession('http://koji.fedoraproject.org/kojihub')

# Generate a list of packages to iterate over
pkgs = ['FlightGear-Atlas', 'IQmol', 'LuxRender', 'Macaulay2', 'MyPasswordSafe', 'OpenImageIO', 'QuantLib', 'Shinobi', 'SimGear', 'SkyX', 'abiword', 'adobe-source-libraries', 'airinv', 'airrac', 'airtsp', 'akonadi', 'anyterm', 'apt-cacher-ng', 'aqsis', 'ardour', 'ardour2', 'ardour3', 'ardour4', 'asc', 'asio', 'assimp', 'autowrap', 'avogadro', 'barry', 'bastet', 'bibletime', 'blender', 'bookkeeper', 'boost-gdb-printers', 'calligra', 'cclive', 'cegui', 'ceph', 'clementine', 'clucene', 'codeblocks', 'collada-dom', 'compat-qpid-cpp', 'console-bridge', 'csdiff', 'csound', 'curlpp', 'cvc4', 'cyphesis', 'dans-gdal-scripts', 'davix', 'device-mapper-persistent-data', 'diet', 'dmlite', 'dmlite-plugins-s3', 'dolphin-connector', 'dyninst', 'easystroke', 'edb', 'ekiga', 'enblend', 'erlang-basho_metrics', 'exempi', 'fawkes', 'fgrun', 'fife', 'fityk', 'flowcanvas', 'freecad', 'fritzing', 'fts', 'fuse-encfs', 'galera', 'gappa', 'gazebo', 'gearmand', 'gecode', 'gfal2-plugin-xrootd', 'gfal2-python', 'glob2', 'glogg', 'glom', 'gnash', 'gnote', 'gnuradio', 'gource', 'gpick', 'gpsdrive', 'gqrx', 'gr-air-modes', 'gr-osmosdr', 'grfcodec', 'gromacs', 'guitarix', 'hamlib', 'highlight', 'hokuyoaist', 'hugin', 'inkscape', 'iwhd', 'k3d', 'kcm_systemd', 'kdenetwork-strigi-analyzers', 'kdepim', 'kdepimlibs', 'kdevelop', 'kdevplatform', 'kea', 'kf5-kactivities', 'kgraphviewer', 'kicad', 'kig', 'kmymoney', 'kpilot', 'kradio4', 'ktorrent', 'ladish', 'launchy', 'libabw', 'libcdr', 'libclaw', 'libcmis', 'libcutl', 'libe-book', 'libepubgen', 'libetonyek', 'libflatarray', 'libftdi', 'libgltf', 'libint2', 'libixion', 'libkindrv', 'libkni3', 'libkolabxml', 'libktorrent', 'liblas', 'libmspub', 'libmwaw', 'libodb-boost', 'libodfgen', 'libopenraw', 'libopkele', 'liborcus', 'liborigin2', 'libpagemaker', 'libpst', 'librecad', 'libreoffice', 'librevenge', 'librime', 'librvngabw', 'libvisio', 'libwps', 'libyui', 'libyui-bindings', 'libyui-gtk', 'libyui-ncurses', 'libyui-qt', 'licq', 'logstalgia', 'lrslib', 'luabind', 'lucene++', 'luminance-hdr', 'lv2-c++-tools', 'lv2-sorcer', 'lyx', 'mapnik', 'mariadb', 'mbox2eml', 'mdds', 'meson', 'mesos', 'milia', 'minion', 'mkvtoolnix', 'mlpack', 'mmseq', 'mongo-cxx-driver', 'mongodb', 'monotone', 'mrpt', 'ncbi-blast+', 'ncmpcpp', 'nemiver', 'nodejs-mapnik', 'nodejs-mapnik-vector-tile', 'normaliz', 'nss-gui', 'ogre', 'ompl', 'openms', 'openoffice.org-diafilter', 'openscad', 'orthanc', 'osm2pgsql', 'oyranos', 'paraview', 'pcl', 'pdfedit', 'pdns', 'pdns-recursor', 'percolator', 'permlib', 'pgRouting', 'pingus', 'plasma-desktop', 'plasma-workspace', 'player', 'plee-the-bear', 'poedit', 'pokerth', 'polybori', 'polymake', 'povray', 'psi4', 'ptlib', 'pulseview', 'pyexiv2', 'python-lmiwbem', 'python-tag', 'python-ufc', 'python-visual', 'qbittorrent', 'qpid-cpp', 'qpid-qmf', 'qt-gstreamer', 'rb_libtorrent', 'rcsslogplayer', 'rcssmonitor', 'rcssserver', 'rcssserver3d', 'resiprocate', 'rmol', 'rocs', 'rospack', 'scantailor', 'schroot', 'scidavis', 'scribus', 'scummvm-tools', 'sdcc', 'sdformat', 'seqan', 'sevmgr', 'shiny', 'sigil', 'sim', 'simcrs', 'simfqt', 'simspark', 'sinfo', 'slic3r', 'smesh', 'snapper', 'soci', 'sord', 'source-highlight', 'source-highlight-qt', 'spring', 'springlobby', 'srecord', 'stdair', 'stellarium', 'stp', 'supertux', 'swift', 'swig', 'swig2', 'sympol', 'syncevolution', 'synfig', 'tcpflow', 'thrift', 'tintii', 'tncfhh', 'tomahawk', 'trademgen', 'trafficserver', 'travelccm', 'uhd', 'umbrello', 'undertaker', 'urbanlightscape', 'urdfdom', 'urg', 'uwsgi', 'valyriatear', 'vdrift', 'vegastrike', 'vfrnav', 'vigra', 'vios-proxy', 'votca-tools', 'vsqlite++', 'vtk', 'websocketpp', 'wesnoth', 'widelands', 'writerperfect', 'wt', 'xboxdrv', 'xmlcopyeditor', 'xmms2', 'xsd', 'xylib', 'yadex', 'yaml-cpp', 'yoshimi', 'zookeeper', 'zorba']

print 'Checking %s packages...' % len(pkgs)

# Loop over each package
for pkg in pkgs:
    name = pkg

    # some package we just dont want to ever rebuild
    if name in pkg_skip_list:
        print 'Skipping %s, package is explicitely skipped' % name
        continue

    # Check out git
    fedpkgcmd = ['fedpkg', 'clone', name]
    print 'Checking out %s' % name
    if runme(fedpkgcmd, 'fedpkg', name, enviro):
        continue

    # Check for a checkout
    if not os.path.exists(os.path.join(workdir, name)):
        sys.stderr.write('%s failed checkout.\n' % name)
        continue

    # Check for a noautobuild file
    #f os.path.exists(os.path.join(workdir, name, 'noautobuild')):
        # Maintainer does not want us to auto build.
    #   print 'Skipping %s due to opt-out' % name
    #   continue

    # check the git hashes of the branches
    gitcmd = ['git', 'rev-parse', 'origin/master']
    print 'getting git hash for master'
    masterhash = runmeoutput(gitcmd, 'git', name, enviro, cwd=os.path.join(workdir, name))
    if masterhash == 0:
        sys.stderr.write('%s has no git hash.\n' % name)
        break
 
    gitcmd = ['git', 'rev-parse', 'origin/%s' % secondbuildtag ]
    print 'getting git hash for %s' % secondbuildtag
    secondhash = runmeoutput(gitcmd, 'git', name, enviro, cwd=os.path.join(workdir, name))
    if secondhash == 0:
        sys.stderr.write('%s has no git hash.\n' % name)
        break

    for branch in [buildtag, secondbuildtag]:
        if branch == buildtag:
            target = targets[0]
        else:
            target = targets[1]

        if branch == secondbuildtag:
            # switch branch
            fedpkgcmd = ['fedpkg', 'switch-branch', secondbuildtag ]
            print 'switching %s to %s' % (name, secondbuildtag)
            if runme(fedpkgcmd, 'fedpkg', name, enviro, cwd=os.path.join(workdir, name)):
                continue

        # Find the spec file
        files = os.listdir(os.path.join(workdir, name))
        spec = ''
        for file in files:
            if file.endswith('.spec'):
                spec = os.path.join(workdir, name, file)
                break

        if not spec:
            sys.stderr.write('%s failed spec check\n' % name)
            continue

        if branch == buildtag or masterhash != secondhash:
            # rpmdev-bumpspec
            bumpspec = ['rpmdev-bumpspec', '-u', user, '-c', comment,
                        os.path.join(workdir, name, spec)]
            print 'Bumping %s' % spec
            if runme(bumpspec, 'bumpspec', name, enviro):
                continue

            # git commit
            commit = ['fedpkg', 'commit', '-p', '-m', comment]
            print 'Committing changes for %s' % name
            if runme(commit, 'commit', name, enviro,
                         cwd=os.path.join(workdir, name)):
                continue
        else:
            gitmergecmd = ['git', 'merge', 'master']
            print "merging master into %s" % secondbuildtag
            if runme(gitmergecmd, 'git', name, enviro,
                         cwd=os.path.join(workdir, name)):
                continue
            # git push
            push = ['git', 'push']
            print 'push changes for %s' % name
            if runme(push, 'push', name, enviro,
                     cwd=os.path.join(workdir, name)):
                continue

        # build
        build = ['fedpkg', 'build', '--nowait', '--background', '--target', target]
        print 'Building %s' % name
        runme(build, 'build', name, enviro, 
              cwd=os.path.join(workdir, name))
