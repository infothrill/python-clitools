# -*- coding: utf-8 -*-

"""Attempt to detect encoding of file specified."""

from __future__ import absolute_import

import sys
import chardet


def main():
    """
    Run main program.

    :param args: command line args
    """
    args = sys.argv[1:]
    if len(args) < 1:
        sys.stderr.write('Please provide one or more filenames.')
        return 1
    for fname in args:
        charencoding = chardet.detect(open(fname, 'rb').read())
        sys.stdout.write('%s:%s (confidence %s)\n' % (fname, charencoding['encoding'],
                                                      int(charencoding['confidence'] * 100)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
