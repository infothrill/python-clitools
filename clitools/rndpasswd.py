#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Generate a random password.

This uses pwgen if available, otherwises uses the
secrets module to generate a password.
"""

from __future__ import absolute_import, print_function

import os
import subprocess  # noqa: S404
import sys
from itertools import islice, repeat
from secrets import token_bytes

import click


def which(program):
    """
    Find executable in PATH just like the unix utility `which`.

    :param program: string path
    """
    def is_exe(fpath):
        """Determine wether file at given path is executable."""
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, _ = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ['PATH'].split(os.pathsep):
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file

    return None


def rand_string(length=32, exclude=None):
    """
    Generate and return a random string.

    :param length: int length of string to generate
    :param exclude: string characters to exclude
    """
    if exclude is None:
        exclude = set()
    else:
        exclude = set(exclude)
    # remove lowercase L and uppercase o to avoid confusion with DIGITS
    lower_case = 'abcdefghijkmnopqrstuvwxyz'
    upper_case = 'ABCDEFGHIJKLMNPQRSTUVWXYZ'
    digits = '0123456789'
    symbols = '!#$%&()*+,-./:;<=>?@[]_}{~^'

    allowed = set(lower_case + upper_case + digits + symbols).difference(exclude)

    def urandomascii(size):
        strval = None
        while strval is None:
            value = token_bytes(size)
            try:
                strval = value.decode('ascii')
            except UnicodeDecodeError:
                strval = None
                continue
        return strval

    char_gen = (c for c in map(urandomascii, repeat(1)) if c in allowed)
    return ''.join(islice(char_gen, None, length))


def pwgen(length=32, exclude=None):
    """
    Run commdand line tool `pwgen` to generate a password.

    :param length: int length of string to generate
    :param exclude: string characters to exclude
    """
    # pwgen -sBy -r "\`'\"" 32 1
    if exclude is None:
        exclude = r"\`'\""
    else:
        exclude = r"\`'\"" + exclude
    cmd = ['pwgen', '-sBy', '-r', exclude, '%s' % length, '1']
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)  # noqa: S603
    stdout, stderr = proc.communicate()
    if proc.returncode != 0:
        raise Exception('pwgen: %s %s' % (stdout, stderr))
    return stdout.strip().decode('ascii')


@click.command()
@click.argument('length', type=click.INT, default=32)
@click.option('-r', '--remove-chars', type=click.STRING, default='')
def main(length, remove_chars):
    """Generate a secure password."""
    if which('pwgen'):
        print(pwgen(length, remove_chars))  # noqa: T201
    else:
        print(rand_string(length, remove_chars))  # noqa: T201
    return 0


if __name__ == '__main__':
    # pylint: disable=no-value-for-parameter
    sys.exit(main())
