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

LOCALKOJIHUB = 'http://sparc.koji.fedoraproject.org/kojihub'
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

tag = 'dist-f15'

ignorelist="kernel anaconda CodeAnalyst-gui Glide3 Glide3-libGL LabPlot R-bigmemory alex alt-ergo acpid apmd apmud athcool bibtex2html biosdevname bluez-hcidump camstream ccid ccsm cdrdao cduce darcs appliance-tools cmospwd cmucl coccinelle compat-gcc-296 compiz-bcop compiz-fusion-extras compiz-fusion-unsupported compizconfig-backend-gconf compizconfig-backend-kconfig compizconfig-python cabal-install compiz-fusion coq coredumper cpufrequtils cpuid cpuspeed csisat compiz hlint dmidecode dvgrab cpphs dssi-vst librdmacm edac-utils efax efibootmgr eject elilo esc ext3grep fbset fedora-ksplice emerald minicom coolkey firecontrol firmware-addon-dell fpc fprint_demo fprintd freeipmi freetennis ghc ghc-GLUT ghc-HUnit ghc-OpenGL ghc-X11 ghc-X11-xft ghc-editline ghc-fgl ghc-ghc-paths ghc-gtk2hs ghc-haskell-src ghc-html ghc-mmap ghc-mtl ghc-parallel ghc-parsec ghc-regex-base ghc-regex-compat ghc-regex-posix ghc-stm ghc-tar ghc-haskeline ghc-xhtml ghc-xmonad-contrib ghc-zlib k3b gkrellm-wifi grub2 gnome-do-plugins ghc-haskell-src-exts gnome-pilot gnome-pilot-conduits ghc-uniplate gnu-efi gpart gphoto2 gprolog openobex gsynaptics ghc-HTTP gtksourceview-sharp jpilot-backup eclipse-cdt happy haskell-platform hdparm hevea pilot-link i2c-tools i8kutils ibmasm ifd-egate grub inkscape ghc-cgi ioport iprutils ipw2100-firmware ipw2200-firmware irda-utils irqbalance isdn4k-utils joystick jpilot flashrom kpilot ksensors ksplice latrace lazarus libavc1394 libbsr libcompizconfig libcxgb3 libdc1394 libfprint hscolour libibcm libibcommon libibverbs libiec61883 libraw1394 librtas libsmbios libspe2 libunwind libusb1 hplip libx86 lightning lrmi obexd gnome-media maxima mcelog mediawiki memtest86+ nut libbtctl mkbootdisk mldonkey mod_mono mono-basic monotone-viz msr-tools nspluginwrapper seabios obex-data-server ocaml ocaml-SDL ocaml-ancient ocaml-augeas ocaml-bisect ocaml-bitstring ocaml-cairo ocaml-calendar ocaml-camlidl ocaml-camlimages ocaml-camlp5 ocaml-camomile ocaml-cil ocaml-cmigrep ocaml-csv ocaml-cryptokit ocaml-curl ocaml-curses ocaml-dbus ocaml-deriving ocaml-expat ocaml-extlib ocaml-facile ocaml-fileutils ocaml-findlib ocaml-gettext ocaml-gsl ocaml-json-static ocaml-json-wheel ocaml-lablgl ocaml-lablgtk ocaml-lacaml ocaml-libvirt ocaml-lwt ocaml-mikmatch ocaml-mlgmpidl ocaml-mysql ocaml-newt ocaml-ocamlgraph ocaml-ocamlnet ocaml-omake ocaml-openin ocaml-ounit ocaml-p3l ocaml-pa-do ocaml-pa-monad ocaml-pcre ocaml-perl4caml ocaml-pgocaml ocaml-postgresql ocaml-preludeml ocaml-pxp ocaml-reins ocaml-res ocaml-sexplib ocaml-sqlite ocaml-ssl ocaml-type-conv ocaml-ulex ocaml-xml-light ocaml-xmlrpc-light ocaml-zip ocamldsort ohm olpc-kbdshim olpc-powerd setserial ghc-dataenc ghc-hashed-storage libdv libibmad libhid pcc xorg-x11-drv-openchrome ghc-binary system-config-kdump libibumad pidgin libcrystalhd picprog planets pmtools podsleuth powerpc-utils powerpc-utils-papr ppc64-utils microcode_ctl procbench ps3-utils pvs-sbcl numactl python-iwlib python-psyco eclipse-changelog pyxf86config openmpi pcmciautils openscada rp-pppoe rpmdepsize s3switch sbcl eclipse-rpm-editor rhythmbox opensm sound-juicer spicctrl spring-installer stapitrace statserial svgalib syslinux sysprof system-config-boot system-config-display tbb ghc-QuickCheck tpb tuxcmd tvtime unetbootin unison213 unison227 valgrind vbetool ghc-network viaideinfo yaboot virt-mem virt-top vrq wacomexpresskeys xenner why wine wraplinux wxMaxima wyrd x86info xen xfce4-sensors-plugin xmonad xorg-x11-drv-acecad xorg-x11-drv-aiptek xorg-x11-drv-apm xorg-x11-drv-ark xorg-x11-drv-ast xorg-x11-drv-chips xorg-x11-drv-cirrus xorg-x11-drv-dummy xorg-x11-drv-elographics xorg-x11-drv-evdev xorg-x11-drv-fbdev xorg-x11-drv-geode xorg-x11-drv-glint xorg-x11-drv-hyperpen xorg-x11-drv-i128 xorg-x11-drv-i740 xorg-x11-drv-intel xorg-x11-drv-ivtv xorg-x11-drv-keyboard xorg-x11-drv-mach64 xorg-x11-drv-mga xorg-x11-drv-mouse xorg-x11-drv-mutouch xorg-x11-drv-neomagic xorg-x11-drv-nv xorg-x11-drv-penmount xorg-x11-drv-r128 xorg-x11-drv-radeonhd xorg-x11-drv-rendition xorg-x11-drv-s3 xorg-x11-drv-s3virge xorg-x11-drv-savage xorg-x11-drv-siliconmotion xorg-x11-drv-sis xorg-x11-drv-sisusb xorg-x11-drv-tdfx xorg-x11-drv-trident xorg-x11-drv-tseng xorg-x11-drv-v4l xorg-x11-drv-vesa xorg-x11-drv-vmware xorg-x11-drv-void xorg-x11-drv-voodoo xsp zenon zfs-fuse xorg-x11-drv-fpit libmlx4 libmthca rxtx xorg-x11-drv-vmmouse xorg-x11-drv-synaptics xorg-x11-drv-nouveau xorg-x11-drv-ati superiotool xorg-x11-drivers xorg-x11-drv-qxl qpid-cpp xorg-x11-drv-wacom openoffice.org"

pkgs = remotekojisession.listPackages(tagID=tag, inherited=True)

pg = progress.TextMeter()

for pkg in pkgs:
    if pkg['package_name'] in ignorelist:
        logging.debug("Ignored package: %s" % pkg['package_name'])
        continue
    if pkg['blocked']:
        logging.debug("Blocked pkg: %s" % pkg['package_name'])
        continue
    pkginfo = remotekojisession.listTagged(tag, inherit=True, package=pkg['package_name'])
    pkgindex = 1
    if len(pkginfo)>1:
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
    # if we have never built the package on our target hub localBuild is None and we want to build it
    if not localBuild == None:
        if localBuild['state'] == 1:
            logging.debug("Local Complete Build: %s" % nvr)
            continue
        else:
            localLatestBuild = localkojisession.getLatestBuilds(tag, package=str(pkg['package_name']))
            if not localLatestBuild == []: 
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
        out = os.open(os.path("%s" % fname), os.O_WRONLY|os.O_CREAT|os.O_TRUNC, 0666)
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
    if target == "dist-rawhide":
        try:
            target = "dist-f%s" % nvr.split("fc")[-1].rsplit('.')[0]
            logging.info("switched target to: %s" % (target,))
        except:
            logging.info("unable to switch target: ")
    if target.startswith("dist-f11"):
        logging.debug("Skiping package: %s" % pkg['package_name'])
        continue

    localkojisession.build(source, target, opts=None, priority=2)
    logging.info("submitted build: %s" % nvr)

