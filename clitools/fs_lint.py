# -*- coding: utf-8 -*-

"""Detect issues with files (permissions, ownership, naming)."""

from __future__ import absolute_import
from __future__ import print_function

import os
import sys
import stat
from pathlib import Path

from class_registry import ClassRegistry, ClassRegistryInstanceCache
import click

linterdex = ClassRegistry('name')


class TestBase(object):
    """Base class for file tests."""

    def __init__(self):  # noqa: D107
        self.failed = []

    def add_failed(self, path):
        """Mark the given path as failed."""
        self.failed.append(path)

    def count_failed(self):
        """Return amount of failed tests."""
        return len(self.failed)


@linterdex.register
class TestWorldWritable(TestBase):
    """Test for world writable files."""

    name = 'worldwritable'

    def test(self, path, st):  # noqa: D102
        if bool(st.st_mode & stat.S_IWOTH):
            self.add_failed(path)


@linterdex.register
class TestWorldReadable(TestBase):
    """Test for world readable files."""

    name = "worldreadable"

    def test(self, path, st):  # noqa: D102
        # we include "other executable" in this test
        if bool(st.st_mode & stat.S_IROTH) or bool(st.st_mode & stat.S_IXOTH):
            self.add_failed(path)


@linterdex.register
class TestWorldReadableDirs(TestBase):
    """Test for world readable dirs."""

    name = "worldreadabledirs"

    def test(self, path, st):  # noqa: D102
        if path.is_dir() and (bool(st.st_mode & stat.S_IROTH) or bool(st.st_mode & stat.S_IXOTH)):
            self.add_failed(path)


@linterdex.register
class TestOwner(TestBase):
    """Test for file ownership."""

    name = "owner"

    def __init__(self):  # noqa: D107
        super().__init__()
        self._uid = os.getuid()

    def test(self, path, st):  # noqa: D102
        if st.st_uid != self._uid:
            self.add_failed(path)


@linterdex.register
class TestGroup(TestBase):
    """Test for group ownership."""

    name = "group"

    def __init__(self):  # noqa: D107
        super().__init__()
        self._gid = os.getgid()

    def test(self, path, st):  # noqa: D102
        if st.st_gid != self._gid:
            self.add_failed(path)


@linterdex.register
class TestWronglyExecutable(TestBase):
    """Test for executable bit on known file types."""

    name = "wronglyexecutable"

    def __init__(self):  # noqa: D107
        super().__init__()
        self._extensions = set([".jpg", ".jpeg", ".doc", ".xml", ".js", ".css",
                                ".png", ".gif", ".ppt", ".vsd", ".xls", ".json",
                                ".html", ".tiff", ".ini", ".java", ".graffle",
                                ".sql", ".jar", ".pdf", ".properties", ".psd",
                                ".rtf", ".dvi", ".log", ".wmf", ".txt", ".bmp",
                                ".tif", ".cdr", ".eps", ".zip", ".avi", ".mp4",
                                ".odt", ".csv", ".ttf", ".xhtml"])
        self.suffixes = {}  # keep an index count of all non-matched, executable extensions
        # useful for optimizing / debugging

    def test(self, path, st):  # noqa: D102
        if not stat.S_ISDIR(st.st_mode):
            if bool(st.st_mode & stat.S_IXUSR) or bool(st.st_mode & stat.S_IXGRP) or bool(st.st_mode & stat.S_IXOTH):
                if path.suffix.lower() in self._extensions:
                    self.add_failed(path)
                else:
                    if path.suffix.lower() not in self.suffixes:
                        self.suffixes[path.suffix.lower()] = 0
                    self.suffixes[path.suffix.lower()] += 1


@linterdex.register
class TestUpperCaseExtension(TestBase):
    """Test for filenames with upper case extensions."""

    name = "uppercaseextension"

    def __init__(self):  # noqa: D107
        super().__init__()
        self._ok_extensions = set([".PL", ".C"])

    def test(self, path, st):  # noqa: D102
        if not stat.S_ISDIR(st.st_mode):
            if path.suffix not in self._ok_extensions and path.suffix.lower() != path.suffix:
                self.add_failed(path)


@linterdex.register
class TestOrphanExecutable(TestBase):
    """Test for files with an orphaned executable bit.

    An orphaned executable bit is an executable bit set without an according
    read bit set.
    """

    name = "orphanexecutablebit"

    def test(self, path, st):  # noqa: D102
        if bool(st.st_mode & stat.S_IXUSR) and not bool(st.st_mode & stat.S_IRUSR):
            self.add_failed(path)
        elif bool(st.st_mode & stat.S_IXGRP) and not bool(st.st_mode & stat.S_IRGRP):
            self.add_failed(path)
        elif bool(st.st_mode & stat.S_IXOTH) and not bool(st.st_mode & stat.S_IROTH):
            self.add_failed(path)

# TODO: check suid bit


class FSLinter(object):
    """The main linter class."""

    def __init__(self):  # noqa: D107
        self.tests = []

    def register(self, test):
        """Register an initialized test based on TestBase."""
        self.tests.append(test)

    def __call__(self, path):
        """Run all registered tests on the specified path."""
        st = path.lstat()
        for test in self.tests:
            test.test(path, st)


@click.command()
@click.argument('paths', type=click.Path(exists=True), nargs=-1)
@click.option('-s', '--skip-test', multiple=True)
@click.option('-v', '--verbose', is_flag=True, default=False)
def main(paths, skip_test, verbose):
    """Find files that fail certain tests."""
    filetests = ClassRegistryInstanceCache(linterdex)
    linter = FSLinter()
    for available_test in linterdex.keys():
        if available_test not in skip_test:
            linter.register(filetests[available_test])
    for start_path in (os.path.expanduser(p) for p in paths):
        if os.path.isdir(start_path):
            for root, dirs, files in os.walk(start_path):
                for relpath in sorted(dirs):
                    linter(Path(os.path.join(root, relpath)))
                for relpath in sorted(files):
                    linter(Path(os.path.join(root, relpath)))
        elif os.path.isfile(start_path):
            linter(Path(start_path))
        else:
            raise ValueError("Invalid argument %r" % start_path)

    for test in linter.tests:
        if test.count_failed() > 0:
            click.secho("%s: " % test.name, nl=False, bold=True)
            click.secho("%i" % test.count_failed(), fg="red", bold=True)
            if verbose:
                for p in test.failed:
                    click.echo(p)
        else:
            click.secho("%s: " % test.name, nl=False, bold=True)
            click.secho("%i" % test.count_failed(), fg="green", bold=True)

#     import operator
#     sorted_x = sorted(filetests["wronglyexecutable"].suffixes.items(), key=operator.itemgetter(1))
#     print(sorted_x)


if __name__ == '__main__':
    # pylint: disable=no-value-for-parameter
    sys.exit(main())
