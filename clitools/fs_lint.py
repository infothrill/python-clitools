# -*- coding: utf-8 -*-

"""Detect issues with files (permissions, ownership, naming)."""

from __future__ import absolute_import
from __future__ import print_function

import os
import sys
import stat
import re
from pathlib import Path
import subprocess  # noqa: S404
import logging
from unidecode import unidecode

from class_registry import ClassRegistry, ClassRegistryInstanceCache
import click
import pathspec
from slugify import slugify

logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(message)s'))
logger.addHandler(handler)
logger.setLevel(logging.INFO)

linterdex = ClassRegistry('name')


class TestBase():
    """Base class for file tests."""

    def __init__(self):  # noqa: D107
        self.failed = []
        self.total = 0  # count total of tests performed

    def add_failed(self, path):
        """Mark the given path as failed."""
        self.failed.append(path)

    def add_ok(self, path):
        """Mark the given path as ok."""
        pass

    def count_failed(self):
        """Return amount of failed tests."""
        return len(self.failed)

    def test(self, path, pathstat):
        """Run the test on path and stat object."""
        raise NotImplementedError('Must be implemented in subclass.')

    def __call__(self, path, pathstat):
        """Run all test on the specified path and stat object."""
        self.total += 1
        return self.test(path, pathstat)


@linterdex.register
class TestNonRegularFiles(TestBase):
    """Test if path is one of file, directory, symbolic link."""

    name = 'nonregular'

    def test(self, path, pathstat):
        """Run the test on path and stat object."""
        if not stat.S_ISDIR(pathstat.st_mode) \
            and not stat.S_ISREG(pathstat.st_mode) \
                and not stat.S_ISLNK(pathstat.st_mode):
            self.add_failed(path)
            return False
        else:
            self.add_ok(path)
            return True


@linterdex.register
class TestWorldWritable(TestBase):
    """Test for world writable files."""

    name = 'worldwritable'

    def test(self, path, pathstat):
        """Run the test on path and stat object."""
        if bool(pathstat.st_mode & stat.S_IWOTH):
            self.add_failed(path)
            return False
        else:
            self.add_ok(path)
            return True


@linterdex.register
class TestWorldReadable(TestBase):
    """Test for world readable/executable paths."""

    name = 'worldreadable'

    def test(self, path, pathstat):
        """Run the test on path and stat object."""
        # we include "other executable" in this test
        # exclude symbolic links from this test
        if not stat.S_ISLNK(pathstat.st_mode) and (bool(pathstat.st_mode & stat.S_IROTH) or
                                                   bool(pathstat.st_mode & stat.S_IXOTH)):
            self.add_failed(path)
            return False
        else:
            self.add_ok(path)
            return True

    def fix(self, path, pathstat):
        """Fix permissions."""
        current = stat.S_IMODE(pathstat.st_mode)
        os.chmod(path, current & ~stat.S_IROTH & ~stat.S_IXOTH)
        # & takes only those bits that both numbers have
        # ~ inverts the bits of a number
        # so x & ~y takes those bits that x has and that y doesn't have


@linterdex.register
class TestSuid(TestBase):
    """Test for paths with SUID bit."""

    name = 'suid'

    def test(self, path, pathstat):
        """Run the test on path and stat object."""
        if bool(pathstat.st_mode & stat.S_ISUID):
            self.add_failed(path)
            return False
        else:
            self.add_ok(path)
            return True


@linterdex.register
class TestBrokenSymlink(TestBase):
    """Test for broken symlinks."""

    name = 'brokensymlink'

    def test(self, path, pathstat):
        """Run the test on path and stat object."""
        if stat.S_ISLNK(pathstat.st_mode) and not os.path.exists(path):
            self.add_failed(path)
            return False
        else:
            self.add_ok(path)
            return True


@linterdex.register
class TestSgid(TestBase):
    """Test for paths with SGID bit."""

    name = 'sgid'

    def test(self, path, pathstat):
        """Run the test on path and stat object."""
        if bool(pathstat.st_mode & stat.S_ISGID):
            self.add_failed(path)
            return False
        else:
            self.add_ok(path)
            return True


@linterdex.register
class TestOtherReadableDirs(TestBase):
    """Test for 'other' readable dirs."""

    name = 'worldreadabledir'

    def test(self, path, pathstat):
        """Run the test on path and stat object."""
        if path.is_dir() and (bool(pathstat.st_mode & stat.S_IROTH) or bool(pathstat.st_mode & stat.S_IXOTH)):
            self.add_failed(path)
            return False
        else:
            self.add_ok(path)
            return True

    def fix(self, path, pathstat):
        """Remove 'other' readable and 'other' executable bit."""
        current = stat.S_IMODE(pathstat.st_mode)
        os.chmod(path, current & ~stat.S_IROTH & ~stat.S_IXOTH)
        # & takes only those bits that both numbers have
        # ~ inverts the bits of a number
        # so x & ~y takes those bits that x has and that y doesn't have


@linterdex.register
class TestOwner(TestBase):
    """Test for file ownership."""

    name = 'owner'

    def __init__(self):  # noqa: D107
        super().__init__()
        self._uid = os.getuid()

    def test(self, path, pathstat):
        """Run the test on path and stat object."""
        if pathstat.st_uid != self._uid:
            self.add_failed(path)
            return False
        else:
            self.add_ok(path)
            return True


@linterdex.register
class TestGroup(TestBase):
    """Test for group ownership."""

    name = 'group'

    def __init__(self):  # noqa: D107
        super().__init__()
        self._gid = os.getgid()

    def test(self, path, pathstat):
        """Run the test on path and stat object."""
        if pathstat.st_gid != self._gid:
            self.add_failed(path)
            return False
        else:
            self.add_ok(path)
            return True


@linterdex.register
class TestWronglyExecutable(TestBase):
    """Test for executable bit on known file types."""

    name = 'wronglyexecutable'

    def __init__(self):  # noqa: D107
        super().__init__()
        self._extensions = {'.jpg', '.jpeg', '.doc', '.xml', '.js', '.css',
                            '.png', '.gif', '.ppt', '.vsd', '.xls', '.json',
                            '.html', '.tiff', '.ini', '.java', '.graffle',
                            '.sql', '.jar', '.mov', '.pdf', '.properties', '.psd',
                            '.rtf', '.dvi', '.log', '.wmf', '.txt', '.bmp',
                            '.tif', '.cdr', '.eps', '.zip', '.avi', '.mp4',
                            '.odt', '.csv', '.ttf', '.xhtml', '.tbz', '.mid',
                            '.ps', '.swf', '.tex', '.vor', '.dot', '.htm', '.wav',
                            '.mp3', '.aif', '.pkg', '.idx', '.dtd', '.psp', '.svg',
                            '.woff'}
        self.suffixes = {}  # keep an index count of all non-matched, executable extensions
        # useful for optimizing / debugging

    def test(self, path, pathstat):
        """Run the test on path and stat object."""
        # exclude directories and symbolic links from this test
        if not stat.S_ISDIR(pathstat.st_mode) and not stat.S_ISLNK(pathstat.st_mode):
            if bool(pathstat.st_mode & stat.S_IXUSR) or \
                bool(pathstat.st_mode & stat.S_IXGRP) or \
                    bool(pathstat.st_mode & stat.S_IXOTH):
                if path.suffix.lower() in self._extensions:
                    self.add_failed(path)
                    return False
                else:
                    if path.suffix.lower() not in self.suffixes:
                        self.suffixes[path.suffix.lower()] = 0
                    self.suffixes[path.suffix.lower()] += 1
        self.add_ok(path)
        return True

    def fix(self, path, pathstat):
        """Fix permissions."""
        current = stat.S_IMODE(pathstat.st_mode)
        os.chmod(path, current & ~stat.S_IXOTH & ~stat.S_IXGRP & ~stat.S_IXUSR)
        # & takes only those bits that both numbers have
        # ~ inverts the bits of a number
        # so x & ~y takes those bits that x has and that y doesn't have


@linterdex.register
class TestUpperCaseExtension(TestBase):
    """Test for filenames with upper case extensions."""

    name = 'uppercaseextension'

    def __init__(self):  # noqa: D107
        super().__init__()
        self._ok_extensions = {'.PL', '.C'}
        # TODO:
        # self._parts_exceptions = ( ("CVS", "Entries.Log"), )

    def test(self, path, pathstat):
        """Run the test on path and stat object."""
        if (not stat.S_ISDIR(pathstat.st_mode) and
                (path.suffix not in self._ok_extensions and
                    path.suffix.lower() != path.suffix)):
            self.add_failed(path)
            return False
        else:
            self.add_ok(path)
            return True


@linterdex.register
class TestOrphanExecutable(TestBase):
    """Test for files with an orphaned executable bit.

    An orphaned executable bit is an executable bit set without an according
    read bit set.
    """

    name = 'orphanexecutablebit'

    def test(self, path, pathstat):
        """Run the test on path and stat object."""
        if bool(pathstat.st_mode & stat.S_IXUSR) and not bool(pathstat.st_mode & stat.S_IRUSR):
            self.add_failed(path)
            return False
        elif bool(pathstat.st_mode & stat.S_IXGRP) and not bool(pathstat.st_mode & stat.S_IRGRP):
            self.add_failed(path)
            return False
        elif bool(pathstat.st_mode & stat.S_IXOTH) and not bool(pathstat.st_mode & stat.S_IROTH):
            self.add_failed(path)
            return False
        else:
            self.add_ok(path)
            return True


@linterdex.register
class TestTempfile(TestBase):
    """Test if file seems to be a temporary file."""

    name = 'tempfile'

    def __init__(self):  # noqa: D107
        super().__init__()
        self._regex = re.compile(r'^(core|.*~|dead.letter|,.*|.*\.v|.*\.emacs_[0-9]*|.*\.[Bb][Aa][Kk]|.*\.swp)$')

    def test(self, path, pathstat):
        """Run the test on path and stat object."""
        if not stat.S_ISDIR(pathstat.st_mode) and self._regex.match(path.name):
            self.add_failed(path)
            return False
        else:
            self.add_ok(path)
            return True


@linterdex.register
class TestProblematicFilenames(TestBase):
    """Test if file has a problematic name, in particular with regards to commands."""

    name = 'problematicname'

    def __init__(self):  # noqa: D107
        super().__init__()
        expressions = [
            r'.*\s+',  # spaces at end
            r'\s+.*',  # spaces at start
            r'.*\s\s+.*',  # 2 or more adjacent spaces
            r'-.*',  # - at start of name
            r'.*\s-.*',  # - after space in name
        ]
        self._regex = re.compile(r'^(%s)$' % '|'.join(expressions))

    def test(self, path, pathstat):
        """Run the test on path and stat object."""
        if self._regex.match(path.name):
            self.add_failed(path)
            return False
        else:
            self.add_ok(path)
            return True


@linterdex.register
class TestLength32(TestBase):
    """Test if filename is longer than 32 characters."""

    name = 'len32'

    def __init__(self):  # noqa: D107
        super().__init__()
        # stop words when fixing/shortening, ie remove these words entirely
        self._stopwords = ('pictures', 'picture', 'images', 'image', 'img')

    def test(self, path, pathstat):
        """Run the test on path and stat object."""
        if len(path.name) > 32:
            self.add_failed(path)
            return False
        else:
            self.add_ok(path)
            return True

    def experimentalfix(self, path, pathstat):
        """Attempt to rename the file to a shorter variant."""
        # demo = ''.join(['#'] * 32)
        # click.echo(demo)
        # click.echo(path.name)
        max_length = 32 - len(path.suffix)
        new_stem_str = slugify(path.stem, max_length=max_length, word_boundary=False, stopwords=self._stopwords)
        new_path = path.with_name(new_stem_str + path.suffix)
        click.echo(new_path.name)
        if new_path.exists():
            click.echo('ERROR: Already exists!')
        else:
            pass
            # path.rename(new_path)
    # other ideas
    # https://grokbase.com/t/python/python-list/085jmdej9z/compress-a-string
    # https://www.gsp.com/cgi-bin/man.cgi?topic=humanzip


@linterdex.register
class TestNonAscii(TestBase):
    """Test if filename is encoded in non ascii."""

    name = 'non-ascii'

    def test(self, path, pathstat):
        """Run the test on path and stat object."""
        if unidecode(path.name) != path.name:
            # click.echo('%s -> %s' % (path.name, newname))
            self.add_failed(path)
            return False
        else:
            self.add_ok(path)
            return True


class FSLinter():
    """The main linter class."""

    def __init__(self):  # noqa: D107
        self.tests = []
        self._verbose = True
        self._fix = False
        self._experimental = False

    def set_verbose(self, verbose):
        """Set the verbosity."""
        self._verbose = verbose

    def set_fix(self, fix):
        """Set the 'fix' option."""
        self._fix = fix

    def set_experimental(self, experimental):
        """Set the 'experimental' option."""
        self._experimental = experimental

    def register(self, test):
        """Register an initialized test based on TestBase."""
        self.tests.append(test)

    def __call__(self, path):
        """Run all registered tests on the specified path."""
        logger.debug('testing: %s' % path)
        st = path.lstat()
        failures = [test for test in self.tests if not test(path, st)]
        if failures:
            click.secho('FAIL[%s]:' % ','.join(sorted(test.name for test in failures)), nl=False, fg='red', bold=False)
            click.echo('%s' % (path))
            if self._fix:
                for failure in failures:
                    if callable(getattr(failure, 'fix', None)):
                        logger.debug("Attempting to fix failure of '%s' for '%s'", failure.name, path)
                        failure.fix(path, st)
                    elif self._experimental and callable(getattr(failure, 'experimentalfix', None)):
                        logger.debug("Attempting to fix failure of '%s' for '%s'", failure.name, path)
                        failure.fix(path, st)
        else:
            if self._verbose:
                click.secho('OK:', nl=False, fg='green', bold=False)
                click.echo('%s' % (path))


def readlines(fname):
    """
    Return tuple with lines from the given file.

    Ignores problems reading the file and returns an empty tuple.

    :param fname: filename
    """
    try:
        with open(fname, 'r') as fh:
            return tuple(fh.read().splitlines())
    except OSError:
        return ()


def walk_filesystem(paths, skip_vcs_ignore, exclude, ignore_spec):
    """Walk the filesystem and yield paths."""
    for start_path in (os.path.expanduser(p) for p in paths):
        if os.path.isdir(start_path):
            for root, dirs, files in os.walk(start_path):
                if not skip_vcs_ignore and '.gitignore' in files:
                    logger.debug('.gitignore found')
                    local_ignore_spec = pathspec.PathSpec(
                        map(
                            pathspec.patterns.GitWildMatchPattern,
                            exclude + readlines(os.path.join(root, '.gitignore'))
                        )
                    )
                else:
                    local_ignore_spec = ignore_spec
                dirs[:] = [d for d in dirs if not local_ignore_spec.match_file(d)]
                for relpath in dirs:
                    yield Path(os.path.join(root, relpath))
                files[:] = [f for f in files if not local_ignore_spec.match_file(f)]
                for relpath in sorted(files):  # TODO revert to non sorted
                    yield Path(os.path.join(root, relpath))
        elif os.path.isfile(start_path):
            yield Path(start_path)
        else:
            raise ValueError('Invalid argument %r' % start_path)


@click.command()
@click.argument('paths', type=click.Path(exists=True), nargs=-1)
@click.option('-D', '--debug', is_flag=True, default=False)
@click.option('--experimental', is_flag=True, default=False, help='Enable experimental features.')
@click.option('--hidden', is_flag=True, default=False, help='Search hidden files.')
@click.option('-l', '--list-tests', is_flag=True, default=False)
@click.option('-s', '--skip-test', multiple=True)
@click.option('--statistics', is_flag=True, default=False)
@click.option('--fix', is_flag=True, default=False)
@click.option(
    '-e', '--exclude', 'exclude',
    metavar='PATTERN',
    multiple=True,
    help='Exclude files/directories matching PATTERN.'
)
@click.option(
    '-U', '--skip-vcs-ignores', 'skip_vcs_ignore',
    is_flag=True,
    default=False,
    help='Ignore VCS ignore files.'
)
@click.option('-v', '--verbose', is_flag=True, default=False, help='Show more information.')
def fs_lint(
    paths, skip_test, list_tests, exclude, verbose, debug, hidden,
    skip_vcs_ignore, statistics, fix, experimental
):
    """Find paths that fail tests."""
    filetests = ClassRegistryInstanceCache(linterdex)
    linter = FSLinter()
    linter.set_verbose(verbose)
    linter.set_fix(fix)
    if list_tests:
        for available_test in sorted(linterdex.keys()):
            click.secho('%s: ' % available_test, nl=False, bold=True)
            click.echo(filetests[available_test].__doc__)
        return 0
    if not paths:
        with click.Context(fs_lint, info_name='fs-lint') as ctx:
            click.echo(fs_lint.get_help(ctx))
            sys.exit(1)
    if debug:
        logger.setLevel(logging.DEBUG)

    if not exclude:
        exclude = ()
    if not skip_vcs_ignore:
        # get global gitignore patterns
        gitexcludes = subprocess.check_output(  # noqa: S607
            'git config --path --get core.excludesfile 2>/dev/null',
            encoding='UTF-8',
            shell=True).strip()  # noqa: S602
        exclude += readlines(gitexcludes)
    if not hidden:
        exclude = ('.*',) + exclude  # assume .* matches most often and takes precedence
    ignore_spec = pathspec.PathSpec(map(pathspec.patterns.GitWildMatchPattern, exclude))

    for available_test in linterdex.keys():
        if available_test not in skip_test:
            linter.register(filetests[available_test])

    for path in walk_filesystem(paths, skip_vcs_ignore, exclude, ignore_spec):
        linter(path)

    if statistics:
        click.secho('Statistics', bold=True)
        for test in linter.tests:
            if test.count_failed() > 0:
                click.secho('%s: ' % test.name, nl=False, bold=False)
                click.secho('%i' % test.count_failed(), fg='red', nl=False, bold=False)
                click.secho('/%i' % (test.total - test.count_failed()), fg='green', bold=False)
            else:
                click.secho('%s: ' % test.name, nl=False, bold=False)
                click.secho('%i' % test.total, fg='green', bold=False)
