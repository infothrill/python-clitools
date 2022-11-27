# -*- coding: utf-8 -*-

"""Look up hostname in ssh config for a given host.

Extremely naive and broken parser implementation using lots of assumptions and
bad regexes. Works for me.
"""
from __future__ import absolute_import, print_function

import os.path
import re
import sys


def main():
    """Run the main program."""
    arg = sys.argv[1]
    filename = os.path.expanduser('~/.ssh/config')

    with open(filename, 'r') as f:
        for line in f.read().split('\n\n'):
            regex = r'[Hh]ost\s+(?P<aliases>[\w+\.\- ]+)\s+[Hh]ostname\s+(?P<hostname>[\w+\.]+)'
            match = re.search(regex, line)
            if match is not None:
                aliases = [x.strip() for x in match.group('aliases').split(' ')]
                if arg in aliases:
                    print(match.group('hostname'))  # noqa: T201
            else:
                continue
    return 0


if __name__ == '__main__':
    sys.exit(main())
