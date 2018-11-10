# -*- coding: utf-8 -*-

"""Simplistic rot13 bi-directional converter."""

from __future__ import absolute_import

import sys


def main():
    """Rot13 convert."""
    for char in sys.stdin.read():
        byte = ord(char)
        cap = (byte & 32)
        byte = (byte & (~cap))
        if (byte >= ord('A')) and (byte <= ord('Z')):
            byte = ((byte - ord('A') + 13) % 26 + ord('A'))
        byte = (byte | cap)
        sys.stdout.write(chr(byte))


if __name__ == '__main__':
    sys.exit(main())
