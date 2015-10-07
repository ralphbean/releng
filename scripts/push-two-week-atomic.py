#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# push-two-week-atomic.py - An utility to sync two-week Atomic releases
#
# For more information about two-week Atomic releases please visit:
#   https://fedoraproject.org/wiki/Changes/Two_Week_Atomic
#
# Copyright (C) 2015 Red Hat, Inc.
# SPDX-License-Identifier:      GPL-2.0+
#
# Authors:
#     Adam Miller <maxamillion@fedoraproject.org>
#
# Exit codes:
#   0 - Success
#   1 - required arg missing
#   2 - no successful AutoCloud builds found
#   3 - subcommand failed, error message will be logged.
#
#

import os
import sys
import json
import glob
import shutil
import fnmatch
import smtplib
import argparse
import logging
import subprocess

import requests

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Set log level to logging.INFO
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(os.path.basename(sys.argv[0]))

# Define "constants"
COMPOSE_BASEDIR = "/mnt/fedora_koji/compose/"

# FIXME ???? Do we need a real STMP server here?
ATOMIC_EMAIL_SMTP = "localhost"
ATOMIC_EMAIL_SENDER = "noreply@fedoraproject.org"

ATOMIC_EMAIL_RECIPIENTS = [
    "cloud@lists.fedoraproject.org",
    "rel-eng@lists.fedoraproject.org",
    "atomic-devel@projectatomic.io",
    "atomic-announce@projectatomic.io",
]

# Full path will be:
#   /pub/alt/stage/$VERSION-$DATE/$IMAGE_TYPE/x86_64/[Images|os]/
# http://dl.fedoraproject.org/pub/alt/atomic/stable/
ATOMIC_TESTING_BASEDIR = "/pub/alt/atomic/testing/"
ATOMIC_STABLE_DESTINATION = "/pub/alt/atomic/stable/"

# the modname gets used to construct the fully qualified topic, like
# 'org.fedoraproject.prod.releng.blahblahblah'
ATOMIC_FEDMSG_MODNAME = "releng"
ATOMIC_FEDMSG_CERT_PREFIX = "releng"

MARK_ATOMIC_BAD_JSON_URL = \
    'https://pagure.io/mark-atomic-bad/raw/master/f/bad-builds.json'
MARK_ATOMIC_BAD_JSON = requests.get(MARK_ATOMIC_BAD_JSON_URL).text
MARK_ATOMIC_BAD_BUILDS = json.loads(MARK_ATOMIC_BAD_JSON)


DATAGREPPER_URL = "https://apps.fedoraproject.org/datagrepper/raw"
# delta = 2 weeks in seconds
DATAGREPPER_DELTA = 1209600
# category to filter on from datagrepper
DATAGREPPER_CATEGORY = "autocloud"


SIGUL_SIGNED_TXT_PATH = "/tmp/signed"


def get_latest_successful_autocloud_test_info(
        datagrepper_url=DATAGREPPER_URL,
        delta=DATAGREPPER_DELTA,
        category=DATAGREPPER_CATEGORY):
    """
    get_latest_successful_autocloud_test_info

        Query datagrepper[0] to find the latest successful Atomic images via
        the autocloud[1] tests.

    return -> dict
        Will return the build information of the latest successful build

    [0] - https://apps.fedoraproject.org/datagrepper/
    [1] - https://github.com/kushaldas/autocloud/
    """

    # rows_per_page is maximum 100 from Fedora's datagrepper
    request_params = {
        "delta": delta,
        "category": category,
        "rows_per_page": 100,
    }
    r = requests.get(datagrepper_url, params=request_params)

    # Start with page 1 response from datagrepper, grab the raw messages
    # and then continue to populate the list with the rest of the pages of data
    autocloud_data = r.json()[u'raw_messages']
    for rpage in range(2, r.json()[u'pages']+1):
        autocloud_data += requests.get(
            datagrepper_url,
            params=dict(page=rpage, **request_params)
        ).json()[u'raw_messages']

    successful_atomic = [
        s for s in autocloud_data
        if s[u'msg'][u'status'] == u'success'
        and s[u'msg'][u'image_name'] == u'Fedora-Cloud-Atomic'
        and not build_manually_marked_bad(
            s[u'msg'][u'image_url'].split('/')[-1]
        )
    ]

    successful_atomic_vagrant = [
        s for s in autocloud_data
        if s[u'msg'][u'status'] == u'success'
        and s[u'msg'][u'image_name'] == u'Fedora-Cloud-Atomic-Vagrant'
        and not build_manually_marked_bad(
            s[u'msg'][u'image_url'].split('/')[-1]
        )
    ]

    successful_autocloud_info = {}

    if successful_atomic:
        successful_autocloud_info["atomic_qcow2"] = {
            "name": successful_atomic[0][u'msg'][u'image_name'],
            "image_name":
                successful_atomic[0][u'msg'][u'image_url'].split('/')[-1],
            "image_url": successful_atomic[0][u'msg'][u'image_url'],
        }

    if successful_atomic_vagrant:
        successful_autocloud_info["atomic_vagrant"] = {
            "name": successful_atomic[0][u'msg'][u'image_name'],
            "image_name":
                successful_atomic[0][u'msg'][u'image_url'].split('/')[-1],
            "image_url": successful_atomic[0][u'msg'][u'image_url'],
        }

    return successful_autocloud_info


def build_manually_marked_bad(build_id, bad_builds=MARK_ATOMIC_BAD_BUILDS):
    """
    build_manually_marked_bad

        Check for a build that has been marked bad manually

        build_id
            Build id of most recently found auto-tested good compose build

    return -> bool
        True if the build was marked bad, else False
    """

    bad = [b for b in bad_builds['bad-builds'] if b == build_id]

    return len(bad) > 0


def send_atomic_announce_email(
        email_filelist,
        mail_receivers=ATOMIC_EMAIL_RECIPIENTS,
        sender_email=ATOMIC_EMAIL_SENDER,
        sender_smtp=ATOMIC_EMAIL_SMTP):
    """
    send_atomic_announce_email

        Send the atomic announce email to the desired recipients

    """

    released_artifacts = []
    released_checksums = []
    for e_file in email_filelist:
        if "CHECKSUM" in e_file:
            released_checksums.append(
                "https://alt.fedoraproject.org{0}".format(e_file)
            )
        else:
            released_artifacts.append(
                "https://alt.fedoraproject.org{0}".format(e_file)
            )

    msg = MIMEMultipart()
    msg['To'] = "; ".join(mail_receivers)
    msg['From'] = "noreply@fedoraproject.org"
    msg['Subject'] = "Fedora Atomic Host Two Week Release Announcement"
    msg.attach(
        MIMEText(
            """
A new update of Fedora Cloud Atomic Host has been released and can be
downloaded at:

Images can be found here:
{0}

Respective signed CHECKSUM files can be found here:
{1}

Thank you,
Fedora Release Engineering
            """.format(
                '\n'.join(released_artifacts),
                '\n'.join(released_checksums)
            )
        )
    )

    # FIXME
    # Need to add package information to fill in the template email
    #
    #   The following changes are included in this update:

    try:
        s = smtplib.SMTP(sender_smtp)
        s.sendmail(sender_email, mail_receivers, msg.as_string())
    except smtplib.SMTPException, e:
        print "ERROR: Unable to send email:\n{0}\n".format(e)


def stage_atomic_release(
        compose_id,
        compose_basedir=COMPOSE_BASEDIR,
        testing_basedir=ATOMIC_TESTING_BASEDIR,
        dest_dir=ATOMIC_STABLE_DESTINATION):
    """
    stage_atomic_release

        stage the release somewhere, this will remove the old and rsync up the
        new twoweek release

    """

    # FIXME - right now the value of compose_id is actually just a date that
    #         we have to glob search for, this should later just be a join
    source_loc = glob.glob(
        os.path.join(
            compose_basedir,
            "*{0}".format(compose_id)
        )
    )[0]

    # FIXME - The --link-dest here is defined based on the stop-gap glob
    #         and should be altered once this is fixed
    rsync_cmd = [
        'rsync -avhHP --delete-after',
        '--link-dest={0}'.format(
            os.path.join(
                testing_basedir,
                source_loc.split('/')[-1]
            )
        ),
        "{0}/*".format(source_loc),
        dest_dir
    ]
    rsync_cmd = ' '.join(rsync_cmd)

    if subprocess.call(rsync_cmd, shell=True):
        log.error(
            "stage_atomic_release: rsync command failed: {0}".format(rsync_cmd)
        )
        exit(3)


def sign_checksum_files(
        key,
        artifact_path,
        signed_txt_path=SIGUL_SIGNED_TXT_PATH):
    """
    sign_checksum_files

        Use sigul to sign checksum files onces we know the successfully tested
        builds.
    """

    # Grab all the checksum_files
    checksum_files = []
    for full_dir_path, _, short_names in os.walk(artifact_path):
        for sname in fnmatch.filter(short_names, '*CHECKSUM'):
            checksum_files.append(
                os.path.join(
                    full_dir_path,
                    sname,
                )
            )

    for cfile in checksum_files:

        # Check to make sure this file isn't already signed, if it is then
        # don't sign it again
        already_signed = False
        with open(cfile, 'r') as f:
            for line in f.readlines():
                if "-----BEGIN PGP SIGNED MESSAGE-----" in line:
                    already_signed = True
                    break
        if already_signed:
            log.info(
                "sign_checksum_files: {0} is already signed".format(cfile)
            )
            continue

        shutil.copy(cfile, signed_txt_path)

        # Basically all of this is ugly and I feel bad about it.
        sigulsign_cmd = [
            "sigul sign-text -o {0} {1} {2}".format(
                signed_txt_path,
                key,
                cfile
            ),
            "&&",
            "chgrp releng {0}".format(signed_txt_path),
            "&&",
            "chmod 664 {0}".format(signed_txt_path),
        ]

        log.info("sign_checksum_files: Signing {0}".format(cfile))
        sigulsign_cmd = ' '.join(sigulsign_cmd)
        while subprocess.call(sigulsign_cmd, shell=True):
            log.warn(
                "sigul command for {0} failed, retrying".format(cfile)
            )

        if subprocess.call(
            "sg releng 'mv {0} {1}'".format(signed_txt_path, cfile),
            shell=True
        ):
            log.error(
                "sign_checksum_files: sg releng 'mv {0} {1}' FAILED".format(
                    signed_txt_path,
                    cfile,
                )
            )
            sys.exit(3)


def fedmsg_publish(topic, msg):
    """ Try to publish a message on the fedmsg bus.

    But proceed happily if we weren't able to publish anything.
    """

    try:
        import fedmsg
        import fedmsg.config

        # Load config from disk with all the environment goodies.
        config = fedmsg.config.load_config()

        # And overwrite some values
        config['modname'] = ATOMIC_FEDMSG_MODNAME
        config['cert_prefix'] = ATOMIC_FEDMSG_CERT_PREFIX
        config['active'] = True

        # Send it.
        fedmsg.publish(topic=topic, msg=msg, **config)
    except Exception:
        # If you didn't know, log.exception automatically logs the traceback.
        log.exception("Failed to publish to fedmsg.")
        # But by passing, we don't let the exception bubble up and kill us.
        pass


if __name__ == '__main__':

    # get args from command line
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-k",
        "--key",
        help="signing key to use with sigul",
    )
    pargs = parser.parse_args()

    if not pargs.key:
        log.error("No key passed, see -h for help")
        sys.exit(1)

    log.info("Querying datagrepper for latest AutoCloud successful tests")
    # Acquire the latest successful builds from datagrepper
    tested_autocloud_info = get_latest_successful_autocloud_test_info()
    log.info("Query to datagrepper complete")
    # If the dict is empty, there were no successful builds in the last two
    # weeks, error accordingly
    if not tested_autocloud_info:
        log.error("No successful builds found")
        sys.exit(2)

    log.info("Sending fedmsg releng.atomic.twoweek.begin")
    fedmsg_publish(
        topic="atomic.twoweek.begin",
        msg=dict(**tested_autocloud_info)
    )

    log.info("Extracting compose_id from the image_url")
    # FIXME - This is a stop-gap until we test against composes and can
    #         identify this properly (also, this is ugly and I'm sorry)
    #
    #       For now this is just a date glob, it should be the compose_id once
    #       autocloud is compose based and references that in it's fedmsg
    #       information
    compose_id = \
        tested_autocloud_info['atomic_qcow2']['image_url'].split(
            '/'
        )[-1].split('.')[0].split('-')[-1]

    log.info("Signing image metadata")
    # FIXME - This is another place where we're having to glob to find the
    #         actual path we want instead of being able to just join the path
    #         using the compose_id
    sign_checksum_files(
        pargs.key,
        glob.glob(
            os.path.join(
                COMPOSE_BASEDIR,
                "*{0}".format(compose_id)
            )
        )[0]
    )

    log.info("Staging release content in /pub/alt/atomic/stable/")
    stage_atomic_release(compose_id)

    log.info("Sending fedmsg releng.atomic.twoweek.complete")
    fedmsg_publish(
        topic="atomic.twoweek.complete",
        msg=dict(**tested_autocloud_info)
    )

    log.info("Sending Two Week Atomic announcement email")
    # Find all the Atomic images and CHECKSUM files to include in the email
    email_filelist = []
    for full_dir_path, _, short_names in os.walk(ATOMIC_STABLE_DESTINATION):
        for sname in fnmatch.filter(short_names, '*Atomic*'):
            email_filelist.append(
                os.path.join(
                    full_dir_path,
                    sname,
                )
            )
            for c_file in glob.glob(os.path.join(full_dir_path, "*CHECKSUM")):
                email_filelist.append(c_file)
    send_atomic_announce_email(set(email_filelist))

    log.info("Two Week Atomic Release Complete!")

# vim: set expandtab sw=4 sts=4 ts=4
