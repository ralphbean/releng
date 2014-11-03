#!/usr/bin/python -tt
# vim: fileencoding=utf8
# SPDX-License-Identifier: GPL-2.0+
# Get signing warnings from mash logs

import argparse
import os
import re


import requests
from bs4 import BeautifulSoup


class MashMonitor(object):
    def __init__(self, release="rawhide", arch="primary"):
        self.release = release
        self.arch = arch

    @property
    def base_url(self):
        if self.arch == "primary":
            return "https://kojipkgs.fedoraproject.org/mash/"
        else:
            return "https://{}.koji.fedoraproject.org/mash/".format(self.arch)

    def get(self, url):
        kwargs = {}
        if self.arch != "primary":
            kwargs["verify"] = os.path.expanduser("~/.fedora-server-ca.cert")
            kwargs["cert"] = os.path.expanduser("~/.fedora.cert")
        return requests.get(url, **kwargs)

    def get_hrefs(self):
        listing_resp = self.get(self.base_url)
        soup = BeautifulSoup(listing_resp.content)

        href_re = re.compile("^{}-[0-9]{{8}}/".format(self.release))

        anchors = soup.find_all("a", attrs={"href": href_re})
        hrefs = sorted([x["href"] for x in anchors])
        return hrefs

    def get_signature_warnings(self, mash_log_url):
        if "://" not in mash_log_url:
            mash_log_url = self.build_mash_log_url(mash_log_url)

        mash_log_response = self.get(mash_log_url)
        mash_log = mash_log_response.content
        signature_check = False
        signature_warnings = []
        for line in mash_log.splitlines():
            if not signature_check and \
                    line.endswith("mash: Checking signatures..."):
                signature_check = True
                continue

            if signature_check:
                if "mash: Writing out files for " in line:
                    break
                else:
                    signature_warnings.append(line)
        return signature_warnings

    def build_mash_log_url(self, href):
        if href[-1] != "/":
            href += "/"

        return self.base_url + href + "logs/mash.log"

    def montitor(self):
        hrefs = self.get_hrefs()
        self.latest_href = hrefs[-1]
        latest_url = self.build_mash_log_url(self.latest_href)
        warnings = self.get_signature_warnings(latest_url)
        return warnings


if __name__ == "__main__":
    parser = argparse.ArgumentParser("Get signing warnings from mash logs")
    parser.add_argument("--releases", default="branched,rawhide")
    parser.add_argument("--archs", default="primary,ppc,arm,s390")
    args = parser.parse_args()
    for arch in args.archs.split(","):
        for release in args.releases.split(","):
            mashmon = MashMonitor(release=release, arch=arch)
            warnings = mashmon.montitor()
            for w in warnings:
                print("{}/{}: {}".format(arch, release, w))
