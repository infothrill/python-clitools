#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Script to convert id3 v1 tags in a mp3 file to id3 v2."""

import sys
import os
import subprocess  # noqa: S404, B404 nosec

# requires tool "id3v2"

# id3v2 -l Prince/Unknown\ Album/When\ Doves\ Cry.mp3
# id3v1 tag info for Prince/Unknown Album/When Doves Cry.mp3:
# Title  : When Doves Cry                  Artist: Prince
# Album  : The Rolling Stone Magazines 50  Year: 1984, Genre: Other (12)
# Comment:                                 Track: 52
# Prince/Unknown Album/When Doves Cry.mp3: No ID3v2 tag

# After conversion:
# id3v1 tag info for Prince/Unknown Album/When Doves Cry.mp3:
# Title  : When Doves Cry                  Artist: Prince
# Album  : The Rolling Stone Magazines 50  Year: 1984, Genre: Other (12)
# Comment:                                 Track: 52
# id3v2 tag info for Prince/Unknown Album/When Doves Cry.mp3:
# TIT2 (Title/songname/content description): When Doves Cry
# TPE1 (Lead performer(s)/Soloist(s)): Prince
# TALB (Album/Movie/Show title): The Rolling Stone Magazines 50
# TYER (Year): 1984
# TRCK (Track number/Position in set): 52
# TCON (Content type): Other (12)


def convert_id3v1_to_id3v2(path):
    """Convert idv3 tags from v1 to v2 using cli tool id3v2."""
    if not os.path.isfile(path):
        raise ValueError('Not a path: {0}'.format(path))
    cmd = ['id3v2', '-C', path]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)  # noqa: S603
    stdout, stderr = proc.communicate()
    if proc.returncode != 0:
        print('Error: non-zero exit code: %i' % proc.returncode)  # noqa: T001
        if len(stdout):
            print(stdout)  # noqa: T001
        if len(stderr):
            print(stderr)  # noqa: T001
    if stderr.find('Tags could not be converted') > -1:
        print('Error: %s' % (stdout + stderr))  # noqa: T001
    return proc.returncode


def get_id3_versions(path):
    """
    Return an array containing 1,2 or nothing.

    :param path: path to mp3
    """
    if not os.path.isfile(path):
        raise ValueError('Not a path: {0}'.format(path))
    cmd = ['id3v2', '-l', path]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)  # noqa: S603
    buf, _err = proc.communicate()
    versions = []
    if buf.find('id3v1 tag info for') > -1:
        versions.append(1)
    if buf.find('id3v2 tag info for') > -1:
        versions.append(2)
    return versions


def main():
    """Run main program."""
    import argparse
    parser = argparse.ArgumentParser(description='Convert id3v1 tags to id3v2 tags.')
    parser.add_argument('paths', metavar='PATH', type=str, nargs='+',
                        help='path to music files')
    parser.add_argument('--dry-run', dest='dryrun', action='store_true',
                        default=False, help='only show affected files')
    parser.add_argument('-v', '--verbose', dest='verbose', action='store_true',
                        default=False, help='list files being inspected')
    args = parser.parse_args()

    for start_path in args.paths:
        for root, _dirs, files in os.walk(start_path):
            for relpath in files:
                abspath = os.path.join(root, relpath)
                if args.verbose:
                    print(abspath)  # noqa: T001
                id3version = get_id3_versions(abspath)
                if id3version:
                    if 1 in id3version and 2 not in id3version:
                        if not args.verbose:
                            print(abspath)  # noqa: T001
                        if not args.dryrun:
                            convert_id3v1_to_id3v2(abspath)
                            print('%r -> %r' % (id3version, get_id3_versions(abspath)))  # noqa: T001


if __name__ == '__main__':
    sys.exit(main())
