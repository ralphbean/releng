#!/usr/bin/env bash

# Copyright (C) 2013 Red Hat Inc.
# SPDX-License-Identifier:	GPL-2.0+

/usr/local/bin/check_epel_deps.py --treename=epel-6 /mnt/koji/mash/updates/el6-epel
/usr/local/bin/check_epel_deps.py --enable-testing --treename=epel-6 /mnt/koji/mash/updates/el6-epel

/usr/local/bin/check_epel_deps.py --treename=epel-5 /mnt/koji/mash/updates/el5-epel
/usr/local/bin/check_epel_deps.py --enable-testing --treename=epel-5 /mnt/koji/mash/updates/el5-epel
