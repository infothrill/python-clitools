#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import fnmatch
from pathlib import Path

import click
from PIL import Image

from autocrop import MultiPartImage, Background


def ac_image(pic, background, dpi=600):
    scan_img = Image.open(pic)
    return MultiPartImage(scan_img, background, dpi)


@click.command()
@click.argument('paths', type=click.Path(exists=True), nargs=-1)
def main(paths):
    scan_path = paths[-1]
    out_path = os.path.join(scan_path, 'autocropped')
    # A saved scan with the scanner empty.
    blank = os.path.join('/Users/pk/Pictures/oldphotos', 'blank.png')
    # A saved scan with multiple photos loaded in the scanner
    blank_img = Image.open(blank)
    background = Background().load_from_image(blank_img, dpi=600)

    FNMATCH = 'SCAN_*.png'
    infiles = []
    for fname in sorted(os.listdir(scan_path)):
        absname = os.path.join(scan_path, fname)
        if not os.path.isfile(absname):
            continue
        if fnmatch.fnmatch(fname, FNMATCH):
            infiles.append(fname)

    for infile in infiles:
        stem = Path(infile).stem
        pic = os.path.join(scan_path, infile)
        for index, photo in enumerate(ac_image(pic, background)):
            dest_path_85 = os.path.join(out_path, '%s-%d.jpg' % (stem, index))
            if not os.path.exists(dest_path_85):
                photo.save(dest_path_85, optimize=True, quality=85)
