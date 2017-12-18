#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Rename filesystem entries to ASCII equivalent transliterations.

Example:

$ ls -l
-rw-r--r--  1 john staff    0 Dec 17 09:15 naïve

$ transliterate -v --dry-run .
./naïve -> naive
"""

# This tool assumes consistent filename encoding. If you are trying to
# fix the encoding of the filenames, try:
# http://manpages.ubuntu.com/manpages/xenial/man1/convmv.1.html

import os
import sys

import click
import six
from unidecode import unidecode


def decode_filesystem_name(value):
    """
    Return unicode representation of filesystem entry.

    :param value: byte or unicode string
    """
    if isinstance(value, six.binary_type):
        value = value.decode(sys.getfilesystemencoding())
    return value


def transrename(path, verbose=False, dry_run=False):
    """
    Rename an individual file or directory to an ASCII transliterated variant.

    :param path: absolute path
    :param verbose: bool
    :param dry_run: bool
    """
    dirname = os.path.dirname(path)
    basename = os.path.basename(path)
    newbasename = unidecode(basename)
    if newbasename != basename:
        newbasename = newbasename.replace('/', '_')  # unicode forward slash allowed, but not ascii!
        newabspath = os.path.join(dirname, newbasename)
        if verbose:
            click.echo("%s -> %s" % (path, newbasename))
        if not dry_run:
            os.rename(path, newabspath)


@click.command()
@click.argument('paths', type=click.Path(exists=True), nargs=-1)
@click.option('-v', '--verbose', is_flag=True, default=False)
@click.option('-d', '--dry-run', is_flag=True, default=False)
def main(paths, verbose, dry_run):
    """Rename filesystem entries to ASCII equivalent transliterations."""
    for start_path in (os.path.expanduser(decode_filesystem_name(p)) for p in paths):
        if os.path.isdir(start_path):
            for root, dirs, files in os.walk(start_path):
                files = [decode_filesystem_name(f) for f in files]
                dirs = [decode_filesystem_name(d) for d in dirs]
                root = decode_filesystem_name(root)

                for relpath in sorted(dirs):
                    transrename(os.path.join(root, relpath), verbose, dry_run)
                for relpath in sorted(files):
                    transrename(os.path.join(root, relpath), verbose, dry_run)
        elif os.path.isfile(start_path):
            transrename(start_path, verbose, dry_run)
        else:
            raise ValueError("Invalid argument %r" % start_path)


if __name__ == '__main__':
    # pylint: disable=no-value-for-parameter
    sys.exit(main())
