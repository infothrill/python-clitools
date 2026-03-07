"""Attempt to detect encoding of file specified."""


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
        with open(fname, 'rb') as f:
            charencoding = chardet.detect(f.read())
            sys.stdout.write('{}:{} (confidence {})\n'.format(fname, charencoding['encoding'],
                                                          int(charencoding['confidence'] * 100)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
