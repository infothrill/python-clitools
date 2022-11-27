#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Dirty hack to script scanning and cropping old photos."""

import fnmatch
import os
from pathlib import Path

import click
from autocrop import Background, MultiPartImage
from PIL import Image


def store_as_jpg(photo, directory, basename, optimize=True, quality=85):
    """Store given photo in directory as jpeg."""
    target = os.path.join(directory, '%s.jpg' % basename)
    new = photo.convert(mode='RGB')
    new.save(target, optimize=optimize, quality=quality)


def store_as_tif(photo, directory, basename, compression='tiff_deflate'):
    """Store given photo in directory as tiff."""
    target = os.path.join(directory, '%s.tif' % basename)
    photo.save(target, compression=compression)


def autocrop_image(fname, outpath, background, dpi=600):
    """Autocrop given file and store cropped results."""
    stem = Path(fname).stem
    scanned_image = Image.open(fname)
    cropped_images = MultiPartImage(scanned_image, background, dpi=600)
    if len(cropped_images) < 2:
        store_as_jpg(scanned_image, outpath, stem)
    else:
        for index, photo in enumerate(cropped_images):
            basename = '%s-%d' % (stem, index)
            store_as_jpg(photo, outpath, basename)


@click.command()
@click.argument('paths', type=click.Path(exists=True), nargs=-1)
def main(paths):
    """Run main program."""
    scan_path = paths[-1]
    out_path = os.path.join(scan_path, 'autocropped')
    # A saved scan with the scanner empty.
    blank = os.path.join('/Users/pk/Pictures/oldphotos', 'blank.png')
    # A saved scan with multiple photos loaded in the scanner
    blank_img = Image.open(blank)
    background = Background().load_from_image(blank_img, dpi=600)

    fnmatchpatterns = ('SCAN_*.png', '*.tif')
    infiles = []
    for fname in sorted(os.listdir(scan_path)):
        absname = os.path.join(scan_path, fname)
        if not os.path.isfile(absname):
            continue
        for fn in fnmatchpatterns:
            if fnmatch.fnmatch(fname, fn):
                infiles.append(fname)
                continue

    for infile in infiles:
        autocrop_image(os.path.join(scan_path, infile), out_path, background)
        # exiftool -DateTimeOriginal="1999:08:11 12:00:0" FILENAME
        # exiftool -v "-DateTimeOriginal>FileModifyDate" FILENAME
