#!/usr/bin/env python

# Copyright (C) 2013 Red Hat Inc,
# SPDX-License-Identifier:	GPL-2.0+
#
# Author: Anthony Towns <atowns@redhat.com>
#
# Bencode parsing code from http://effbot.org/zone/bencode.htm

import sys, re, time, os

import re

def tokenize(text, match=re.compile("([idel])|(\d+):|(-?\d+)").match):
    i = 0
    while i < len(text):
        m = match(text, i)
        s = m.group(m.lastindex)
        i = m.end()
        if m.lastindex == 2:
            yield "s"
            yield text[i:i+int(s)]
            i = i + int(s)
        else:
            yield s

def decode_item(next, token):
    if token == "i":
        # integer: "i" value "e"
        data = int(next())
        if next() != "e":
            raise ValueError
    elif token == "s":
        # string: "s" value (virtual tokens)
        data = next()
    elif token == "l" or token == "d":
        # container: "l" (or "d") values "e"
        data = []
        tok = next()
        while tok != "e":
            data.append(decode_item(next, tok))
            tok = next()
        if token == "d":
            data = dict(zip(data[0::2], data[1::2]))
    else:
        raise ValueError
    return data

def decode(text):
    try:
        src = tokenize(text)
        data = decode_item(src.next, src.next())
        for token in src: # look for more tokens
            raise SyntaxError("trailing junk")
    except (AttributeError, ValueError, StopIteration):
        raise SyntaxError("syntax error")
    return data

def main(argv):
    if len(argv) < 2:
        print "Usage: %s <group> <date>" % (argv[0])
        sys.exit(0)
    group = argv[1]
    if len(argv) >= 3:
        date = argv[2]
    else:
        date = time.strftime("%Y-%m-%d")
    genini(sys.stdout, ".", group,  date)

def SIprefix(n):
    prefix = ["", "k", "M", "G", "T"]
    x = "%d" % (n)
    while len(prefix) > 1 and n > 1024:
        n /= 1024.0
        x = "%.1f" % (n)
        prefix.pop(0)
    return "%s%sB" % (x, prefix[0])
   
def torrentsize(filename):
    torrentdict = decode(open(filename).read())
    length = sum(y["length"] for y in torrentdict["info"]["files"])
    return SIprefix(length) 

def genini(output, path, group,  date):
    for dirpath, dirnames, filenames in os.walk(path):
    	dirnames.sort()
    	filenames.sort()
    	for f in filenames:
            if not f.endswith(".torrent"):
            	continue
	    filepath = os.path.join(dirpath, f)
            displaypath = filepath
            if displaypath.startswith(dirpath):
                displaypath = displaypath[len(dirpath):]
            if displaypath.startswith("/"):
                displaypath = displaypath[1:]
	    size = torrentsize(filepath)
	    output.write("[%s]\n" % (displaypath))
	    output.write("description=%s\n" % (f[:-8].replace("-", " ")))
            output.write("size=%s\n" % (size))
	    output.write("releasedate=%s\n" % (date))
            output.write("group=%s\n" % (group))
    	    output.write("\n")

if __name__ == "__main__":
    main(sys.argv)
