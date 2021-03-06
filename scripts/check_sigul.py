#!/usr/bin/python -tt
# vim: fileencoding=utf8
# SPDX-License-Identifier: GPL-2.0+

import getpass
import logging
log = logging.getLogger(__name__)
import os
import time

from sigulsign_unsigned import SigulHelper
from autosigner import SubjectSMTPHandler


if __name__ == "__main__":
    formatter = logging.Formatter(
        '%(asctime)s: %(levelname)s: %(message)s',
    )
    # Log in UTC
    formatter.converter = time.gmtime

    console_logger = logging.StreamHandler()
    console_logger.setLevel(logging.DEBUG)
    console_logger.setFormatter(formatter)
    log.setLevel(logging.DEBUG)
    log.addHandler(console_logger)

    # FIXME: Make this a config option
    fedora_user = getpass.getuser()
    mail_from = "nobody@fedoraproject.org"
    mail_to = [fedora_user, "releng-cron@lists.fedoraproject.org"]
    mail_logger = SubjectSMTPHandler(
        "127.0.0.1", mail_from, mail_to, "Sigul check log event")
    mail_logger.subject_prefix = "Sigul check: "
    mail_logger.setLevel(logging.WARNING)
    mail_logger.setFormatter(formatter)
    log.addHandler(mail_logger)

    keys = ["fedora-22", "fedora-22-secondary"]
    helpers = {}

    for k in keys:
        log.debug("Monitoring key " + k)
        if k.endswith("-secondary"):
            config_file = os.path.expanduser("~/.sigul/client-secondary.conf")
        else:
            config_file = None

        helpers[k] = SigulHelper(k, config_file=config_file,
                                 ask_with_agent=True, ask=True)

        status = {}

    log.debug("Starting checking...")
    while True:
        for key, helper in helpers.items():
            res = helper.get_public_key()
            ret, pubkey, errors = res
            if ret != 0 or errors:
                log.debug("Key '{}' not working {}:{}".format(
                    key, ret, errors))
            else:
                log.debug("Key '{}' working".format(key))

            if status.get(key, res) != res:
                if ret != 0 or errors:
                    log.error(
                        "Sigul for key '{}' stopped working: {}:{}".format(
                            key, ret, errors))
                else:
                    log.warning(
                        "Sigul for key '{}' resumed working".format(key))

            status[key] = res

        time.sleep(600)
