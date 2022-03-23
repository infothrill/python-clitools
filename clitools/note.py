# -*- coding: utf-8 -*-

"""Command line script to create notes with vim and templates.

The basic concept is to manage notes within a tree of directories like this:

meetings/
        daily/
        weekly/
        planning/
        reporting/

or this:

one-on-ones/
           alice/
           bob/

or this:

interviews/
           backend-engineer-coding/
           backend-engineer-system-design/
           engineering-manager/


or this:

journals/
         plants/
         fitness/
         mediation/


To use the tool, it is assumed that you switch your working directory to the
respective base directory (aka 'meetings') and then run 'note'.

A dialogue showing the subdirectories will be presented to chose from.
A new note file will be created in that sub-folder.

A template located within the target folder (for example 'planning')
or the base folder ('meeting') will be used, in that order.
The template is optional and expected to be called `__template__.md`.

If a file called `__suffix__` is present, an interactive dialogue will be
presented and the contents of that file will be shown. The input will be used
as a suffix for the created filename.
"""

import os
from io import StringIO
import datetime
import tempfile
import logging
import shutil
import click


def fzf(options):
    """Present an fzf style interface for given options."""
    from pyfzf.pyfzf import FzfPrompt
    _fzf = FzfPrompt()
    result = _fzf.prompt(options)
    # print(result)
    return result


def runvi(path):
    """Run vim and exec to it with the given path."""
    shellscript = StringIO()
    shellscript.write('#!/bin/sh\n')
    shellscript.write('# auto-generated shell script\n')
    shellscript.write('vim %s\n' % path)
    fd, temp_name = tempfile.mkstemp('sh', 'vim-wrapper')
    shellscript.write('rm -f {0}\n'.format(temp_name))
    with open(temp_name, 'w') as fpshell:
        fpshell.write(shellscript.getvalue())
    os.close(fd)
    logging.debug(shellscript.getvalue())
    logging.debug('Executing %s', temp_name)
    os.execv('/bin/sh', ('-c', temp_name))  # noqa: S606


def names():
    """Return names of subdirectories of cwd()."""
    li = os.listdir(os.getcwd())
    li = [d for d in li if os.path.isdir(d)]
    return li


def note():
    """Run note program."""
    basepath = os.getcwd()
    NOTES_PATH = basepath
    if not os.path.isdir(NOTES_PATH):
        raise RuntimeError('{0} is not a directory'.format(NOTES_PATH))

    result = fzf(sorted(names()))
    if len(result) == 0:
        return 0  # exit on demand
    option = result[-1]
    if not os.path.isdir(option):
        raise RuntimeError('{0} is not a directory'.format(option))

    targetpath = os.path.join(NOTES_PATH, option)
    if not os.path.isdir(targetpath):
        raise RuntimeError('{0} is not a directory'.format(targetpath))

    suffix = None
    _suffix_question_path = os.path.join(targetpath, '__suffix__')
    if os.path.isfile(_suffix_question_path):
        with open(_suffix_question_path, 'r') as f:
            suffix_question = f.read().strip()
            suffix = input(suffix_question).strip()

    now = datetime.datetime.now()
    fname = None
    if suffix is None:
        fname = '%s.md' % now.strftime('%Y-%m-%d')
    else:
        fname = '%s-%s.md' % (now.strftime('%Y-%m-%d'), suffix)
    targetfname = os.path.join(targetpath, fname)
    if not os.path.exists(targetfname):
        _tpl_path = os.path.join(targetpath, '__template__.md')
        if os.path.exists(_tpl_path):
            shutil.copyfile(_tpl_path, targetfname)
        else:
            # try parent directory
            _tpl_path = os.path.join(NOTES_PATH, '__template__.md')
            if os.path.exists(_tpl_path):
                shutil.copyfile(_tpl_path, targetfname)
    runvi(targetfname)


@click.command()
def main():
    """
    Run command line interface.

    :param nt: Note type
    """
    note()
    return 0
