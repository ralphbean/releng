#!/usr/bin/python


import os
import koji
import logging
import urlgrabber.grabber as grabber
import urlgrabber.progress as progress
import urllib2
import time
import random
import string
import rpm 
import shutil
import operator

LOCALKOJIHUB = 'http://arm.koji.fedoraproject.org/kojihub'
REMOTEKOJIHUB = 'http://koji.fedoraproject.org/kojihub'
PACKAGEURL = 'http://kojipkgs.fedoraproject.org/'

# Should probably set these from a koji config file
SERVERCA = os.path.expanduser('~/.fedora-server-ca.cert')
CLIENTCA = os.path.expanduser('~/.fedora-server-ca.cert')
CLIENTCERT = os.path.expanduser('~/.fedora.cert')

workpath = '/tmp/build-recent'

loglevel = logging.DEBUG
logging.basicConfig(format='%(levelname)s: %(message)s',
                    level=loglevel)

def _unique_path(prefix):
    """Create a unique path fragment by appending a path component
    to prefix.  The path component will consist of a string of letter and numbers
    that is unlikely to be a duplicate, but is not guaranteed to be unique."""
    # Use time() in the dirname to provide a little more information when
    # browsing the filesystem.
    # For some reason repr(time.time()) includes 4 or 5
    # more digits of precision than str(time.time())
    return '%s/%r.%s' % (prefix, time.time(),
                      ''.join([random.choice(string.ascii_letters) for i in range(8)]))

def _rpmvercmp ((e1, v1, r1), (e2, v2, r2)):
    """find out which build is newer"""
    rc = rpm.labelCompare((e1, v1, r1), (e2, v2, r2))
    if rc == 1:
        #first evr wins
        return 1
    elif rc == 0:
        #same evr
        return 0
    else:
        #second evr wins
        return -1

def isNoarch(rpms):
    if not rpms:
        return False
    noarch = False
    for rpminfo in rpms:
        if rpminfo['arch'] == 'noarch':
            #note that we've seen a noarch rpm
            noarch = True
        elif rpminfo['arch'] != 'src':
            return False
    return noarch

def tagSuccessful(nvr, tag):
    """tag completed builds into final tags"""
    localkojisession.tagBuildBypass(tag, nvr)
    print "tagged %s to %s" % (nvr, tag)

def _downloadURL(url, destf):
    """Download a url and save it to a file"""
    file = grabber.urlopen(url, progress_obj = pg, text = "%s" % (destf))

    out = os.open(destf, os.O_WRONLY|os.O_CREAT|os.O_TRUNC, 0666)
    try:
        while 1:
            buf = file.read(4096)
            if not buf:
                break
            os.write(out, buf)
    finally:
        os.close(out)
        file.close()

def _importURL(url, fn):
    """Import an rpm directly from a url"""
    serverdir = _unique_path('build-recent')
    #TODO - would be possible, using uploadFile directly, to upload without writing locally.
    #for now, though, just use uploadWrapper
    koji.ensuredir(workpath)
    dst = "%s/%s" % (workpath, fn)
    print "Downloading %s to %s..." % (url, dst)
    _downloadURL(url, dst)
    #fsrc = urllib2.urlopen(url)
    #fdst = file(dst, 'w')
    #shutil.copyfileobj(fsrc, fdst)
    #fsrc.close()
    #fdst.close()
    print "Uploading %s..." % dst
    localkojisession.uploadWrapper(dst, serverdir, blocksize=65536)
    localkojisession.importRPM(serverdir, fn)

def importBuild(build, rpms, buildinfo, tag=None):
    '''import a build from remote hub'''
    for rpminfo in rpms:
        if rpminfo['arch'] == 'src':
            srpm = rpminfo
    pathinfo = koji.PathInfo(PACKAGEURL)
    build_url = pathinfo.build(buildinfo)
    url = "%s/%s" % (pathinfo.build(buildinfo), pathinfo.rpm(srpm))
    fname = "%s.src.rpm" % build
    _importURL(url, fname)
    for rpminfo in rpms:
        if rpminfo['arch'] == 'src':
            #already imported above
            continue
        relpath = pathinfo.rpm(rpminfo)
        url = "%s/%s" % (build_url, relpath)
        logging.debug("url: %s" % url)
        fname = os.path.basename(relpath)
        logging.debug("fname: %s" % fname)
        _importURL(url, fname)
    tagSuccessful(build, tag)
    return True

# setup the koji session
logging.info('Setting up koji session')
localkojisession = koji.ClientSession(LOCALKOJIHUB)
remotekojisession = koji.ClientSession(REMOTEKOJIHUB)
localkojisession.ssl_login(CLIENTCERT, CLIENTCA, SERVERCA)

tag = 'f18-rebuild'

ignorelist="Agda amtu aunit adobe-source-libraries acpid apmd apmud athcool bunny blktap biosdevname cpuid clean cabal-dev cmospwd cmucl compat-gcc-296 darktable dmidecode darcs dyninst dssi-vst efibootmgr edac-utils edb fedora-ksplice frysk florist firmware-addon-dell groonga ghc-aeson ghc-mwc-random gnu-efi ghc-ForSyDe ghc-Agda GtkAda gprbuild grub ghdl grub2 ghc-hakyll ghc-hamlet gnatcoll gpart gprolog ghc-vector ghc-hashtables ghc-parameterized-data ghc-shakespeare ghc-type-level i8kutils ibmasm imvirt infiniband-diags ioport iprutils ipw2100-firmware ipw2200-firmware ksplice latrace libbsr libipathverbs libseccomp librtas lightning lrmi libsmbios matreshka mactel-boot memtest86+ maxima microcode_ctl mkbootdisk mcelog mono-debugger msr-tools numactl numad openscada openni openni-primesense openalchemist pcc perftest pesign php-pecl-xhprof planets pmtools powerpc-utils powerpc-utils-papr ppc64-utils ps3-utils picprog pvs-sbcl perl-threads-tbb qperf rubygem-virt-p2v s3switch semantik sgabios sbcl syslinux seabios spicctrl stripesnoop spice-xpi sugar-tamtam superiotool svgalib sysprof system-config-boot spice tboot tbb unetbootin virt-v2v vrq wraplinux x86info xen xorg-x11-drv-openchrome xorg-x11-drv-neomagic xorg-x11-drv-geode xorg-x11-drv-vmware xorg-x11-drv-vmmouse xorg-x11-drv-intel yaboot zeromq-ada"

pkgs = remotekojisession.listPackages(tagID=tag, inherited=True)

# reduce the list to those that are not blocked and sort by package name
pkgs = sorted([pkg for pkg in pkgs if not pkg['blocked']],
              key=operator.itemgetter('package_name'))

print 'Checking %s packages...' % len(pkgs)

pg = progress.TextMeter()

for pkg in pkgs:
    if pkg['package_name'] in ignorelist:
        logging.debug("Ignored package: %s" % pkg['package_name'])
        continue
    if pkg['blocked']:
        logging.debug("Blocked pkg: %s" % pkg['package_name'])
        continue
    pkginfo = remotekojisession.listTagged(tag, inherit=False, package=pkg['package_name'])
    pkgindex = 0
    if len(pkginfo) > pkgindex:
        logging.info("got build %s" % pkginfo[pkgindex]['nvr'])
    elif len(pkginfo)==1:
        pkgindex = 0
        logging.info("no previous build for %s" % pkg['package_name'])
        logging.info("reverting to current %s" % pkginfo[pkgindex]['nvr'])
    else:
       # We apparently have 0 builds for this package!
       logging.info("no builds for %s - skipping" % pkg['package_name'])
       continue
    nvr = pkginfo[pkgindex]['nvr']
    name = pkginfo[pkgindex]['package_name']
    epoch = pkginfo[pkgindex]['epoch']
    version = pkginfo[pkgindex]['version']
    release =  pkginfo[pkgindex]['release']
    build_id = pkginfo[pkgindex]['build_id']
    task_id = pkginfo[pkgindex]['task_id']


    # check if we have the nvr built or not
    localBuild = localkojisession.getBuild(nvr)
    # if we have never built the nvr on our target hub localBuild is None localLatestBuild wil be empty as well if we have never built it
    # in which case we have nothing to compare and we need to build it
    localLatestBuild = localkojisession.getLatestBuilds(tag, package=str(pkg['package_name']))
    if not localBuild == None and not localLatestBuild == []:
        if localBuild['state'] == 1:
            logging.debug("Local Complete Build: %s" % nvr)
            continue
        else:
            parentevr = (str(epoch), version,  release)
            latestevr =  (str(localLatestBuild[0]['epoch']), localLatestBuild[0]['version'], localLatestBuild[0]['release'])
            newestRPM = _rpmvercmp( parentevr, latestevr)
            logging.debug("remote evr: %s  \nlocal evr: %s \nResult: %s" % (parentevr, latestevr, newestRPM))
            if newestRPM == -1:
                logging.info("Newer locally: %s locally is newer than remote" % (latestevr,))
                continue
            if newestRPM == 0:
                logging.info("Already Built: %s " % (latestevr,))
                continue
    rpms = remotekojisession.listRPMs(build_id)
    if isNoarch(rpms):
        buildinfo = remotekojisession.getBuild(build_id)
        importBuild(nvr, rpms, buildinfo, tag=tag)
        continue
    request = remotekojisession.getTaskRequest(task_id)
    #localkojisession.build(request[0], request[1], opts=None, priority=2)
        
    fname = "%s.src.rpm" %  nvr
    fpath = "%s/%s.src.rpm" % (workpath, nvr)
    url = "%s/packages/%s/%s/%s/src/%s" % (PACKAGEURL, name, version, release, fname)


    if not os.path.isfile(fpath):
        file = grabber.urlopen(url, progress_obj = pg, text = "%s" % (fname))
        out = os.open(fpath, os.O_WRONLY|os.O_CREAT|os.O_TRUNC, 0666)
        try:
            while 1:
                buf = file.read(4096)
                if not buf:
                    break
                os.write(out, buf)
        finally:
            os.close(out)
            file.close()
        
    serverdir = _unique_path('cli-build')
    localkojisession.uploadWrapper(fpath, serverdir, blocksize=65536)
    source = "%s/%s" % (serverdir, fname)
    target = request[1]
    if target == "rawhide":
        try:
            target = "f%s" % nvr.split("fc")[-1].rsplit('.')[0]
            logging.info("switched target to: %s" % (target,))
        except:
            logging.info("unable to switch target: ")
    if target.startswith("dist-f11"):
        logging.debug("Skiping package: %s" % pkg['package_name'])
        continue

    localkojisession.build(source, target, opts=None, priority=2)
    logging.info("submitted build: %s" % nvr)

