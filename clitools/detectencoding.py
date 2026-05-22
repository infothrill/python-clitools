"""Attempt to detect encoding of file specified."""

import sys

import chardet


def main():
    """Run main program.

    :param args: command line args
    """
    args = sys.argv[1:]
    if len(args) < 1:
        sys.stderr.write('Please provide one or more filenames.')
        return 1
    for fname in args:
        with open(fname, 'rb') as f:
            c = chardet.detect(f.read())  # noqa F841
            sys.stdout.write("{fname}:{c['encoding']} (confidence {c['confidence']})\n")
    return 0


if __name__ == '__main__':
    sys.exit(main())
