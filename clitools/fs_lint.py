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
import difflib
import unicodedata

from unidecode import unidecode
from class_registry import ClassRegistry, ClassRegistryInstanceCache
import click
import pathspec
from slugify import slugify
from colorama import Fore, Style

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
        self.ok = []
        self.total = 0  # count total of tests performed

    def add_failed(self, path):
        """Mark the given path as failed."""
        self.failed.append(path)

    def add_ok(self, path):
        """Mark the given path as ok."""
        self.ok.append(path)

    def count_failed(self):
        """Return amount of failed tests."""
        return len(self.failed)

    def _test(self, path, pathstat):
        """Run the test on path and stat object."""
        raise NotImplementedError('Must be implemented in subclass.')

    def test(self, path, pathstat):
        """Run the test on path and stat object."""
        if self._test(path, pathstat):
            self.add_ok(path)
            return True
        else:
            self.add_failed(path)
            return False

    def __call__(self, path, pathstat):
        """Run all test on the specified path and stat object."""
        self.total += 1
        return self.test(path, pathstat)


@linterdex.register
class TestTypeNonRegular(TestBase):
    """Test if path is one of file, directory, symbolic link."""

    name = 'type-non-regular'

    def _test(self, path, pathstat):
        """Run the test on path and stat object."""
        if not stat.S_ISDIR(pathstat.st_mode) \
            and not stat.S_ISREG(pathstat.st_mode) \
                and not stat.S_ISLNK(pathstat.st_mode):
            return False
        else:
            return True


@linterdex.register
class TestPermissionsWorldWritable(TestBase):
    """Test for world writable files."""

    name = 'permissions-world-writable'

    def _test(self, path, pathstat):
        """Run the test on path and stat object."""
        # exclude symbolic links from this test
        if not stat.S_ISLNK(pathstat.st_mode) and bool(pathstat.st_mode & stat.S_IWOTH):
            return False
        else:
            return True

    def fix(self, path, pathstat):
        """Fix permissions."""
        current = stat.S_IMODE(pathstat.st_mode)
        os.chmod(path, current & ~stat.S_IWOTH)
        # & takes only those bits that both numbers have
        # ~ inverts the bits of a number
        # so x & ~y takes those bits that x has and that y doesn't have


@linterdex.register
class TestPermissionsWorldReadable(TestBase):
    """Test for world readable/executable paths."""

    name = 'permissions-world-readable'

    def _test(self, path, pathstat):
        """Run the test on path and stat object."""
        # we include "other executable" in this test
        # exclude symbolic links from this test
        if not stat.S_ISLNK(pathstat.st_mode) and (bool(pathstat.st_mode & stat.S_IROTH) or
                                                   bool(pathstat.st_mode & stat.S_IXOTH)):
            return False
        else:
            return True

    def fix(self, path, pathstat):
        """Fix permissions."""
        current = stat.S_IMODE(pathstat.st_mode)
        os.chmod(path, current & ~stat.S_IROTH & ~stat.S_IXOTH)
        # & takes only those bits that both numbers have
        # ~ inverts the bits of a number
        # so x & ~y takes those bits that x has and that y doesn't have


@linterdex.register
class TestPermissionsSuid(TestBase):
    """Test for paths with SUID bit."""

    name = 'permissions-suid'

    def _test(self, path, pathstat):
        """Run the test on path and stat object."""
        if bool(pathstat.st_mode & stat.S_ISUID):
            return False
        else:
            return True


@linterdex.register
class TestTypeBrokenSymlink(TestBase):
    """Test for broken symlinks."""

    name = 'type-broken-symlink'

    def _test(self, path, pathstat):
        """Run the test on path and stat object."""
        if stat.S_ISLNK(pathstat.st_mode) and not os.path.exists(path):
            return False
        else:
            return True


@linterdex.register
class TestPermissionsSgid(TestBase):
    """Test for paths with SGID bit."""

    name = 'permissions-sgid'

    def _test(self, path, pathstat):
        """Run the test on path and stat object."""
        if bool(pathstat.st_mode & stat.S_ISGID):
            return False
        else:
            return True


@linterdex.register
class TestPermissionsWorldReadableDir(TestBase):
    """Test for 'other' readable dirs."""

    name = 'permissions-world-readable-dir'

    def _test(self, path, pathstat):
        """Run the test on path and stat object."""
        # skip symlinks
        if not stat.S_ISLNK(pathstat.st_mode) and path.is_dir() and \
                (bool(pathstat.st_mode & stat.S_IROTH) or bool(pathstat.st_mode & stat.S_IXOTH)):
            return False
        else:
            return True

    def fix(self, path, pathstat):
        """Remove 'other' readable and 'other' executable bit."""
        current = stat.S_IMODE(pathstat.st_mode)
        os.chmod(path, current & ~stat.S_IROTH & ~stat.S_IXOTH)
        # & takes only those bits that both numbers have
        # ~ inverts the bits of a number
        # so x & ~y takes those bits that x has and that y doesn't have


@linterdex.register
class TestPermissionsOwner(TestBase):
    """Test for file ownership."""

    name = 'permissions-owner'

    def __init__(self):  # noqa: D107
        super().__init__()
        self._uid = os.getuid()

    def _test(self, path, pathstat):
        """Run the test on path and stat object."""
        if pathstat.st_uid != self._uid:
            return False
        else:
            return True


@linterdex.register
class TestPermissionsGroup(TestBase):
    """Test for group ownership."""

    name = 'permissions-group'

    def __init__(self):  # noqa: D107
        super().__init__()
        self._gid = os.getgid()

    def _test(self, path, pathstat):
        """Run the test on path and stat object."""
        if pathstat.st_gid != self._gid:
            return False
        else:
            return True


@linterdex.register
class TestPermissionsWronglyExecutable(TestBase):
    """Test for executable bit on known file types."""

    name = 'permissions-wrongly-executable'

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

    def _test(self, path, pathstat):
        """Run the test on path and stat object."""
        # exclude directories and symbolic links from this test
        if not stat.S_ISDIR(pathstat.st_mode) and not stat.S_ISLNK(pathstat.st_mode):
            if bool(pathstat.st_mode & stat.S_IXUSR) or \
                bool(pathstat.st_mode & stat.S_IXGRP) or \
                    bool(pathstat.st_mode & stat.S_IXOTH):
                if path.suffix.lower() in self._extensions:
                    return False
                else:
                    if path.suffix.lower() not in self.suffixes:
                        self.suffixes[path.suffix.lower()] = 0
                    self.suffixes[path.suffix.lower()] += 1
        return True

    def fix(self, path, pathstat):
        """Fix permissions."""
        current = stat.S_IMODE(pathstat.st_mode)
        os.chmod(path, current & ~stat.S_IXOTH & ~stat.S_IXGRP & ~stat.S_IXUSR)
        # & takes only those bits that both numbers have
        # ~ inverts the bits of a number
        # so x & ~y takes those bits that x has and that y doesn't have


@linterdex.register
class TestNameUpperCaseExtension(TestBase):
    """Test for filenames with upper case extensions."""

    name = 'name-uppercase-extension'

    def __init__(self):  # noqa: D107
        super().__init__()
        self._ok_extensions = {'.PL', '.C'}
        # TODO:
        # self._parts_exceptions = ( ("CVS", "Entries.Log"), )

    def _test(self, path, pathstat):
        """Run the test on path and stat object."""
        if (not stat.S_ISDIR(pathstat.st_mode) and
                (path.suffix not in self._ok_extensions and
                    path.suffix.lower() != path.suffix)):
            return False
        else:
            return True

    def fix(self, path, pathstat):
        """Fix upper case extension."""
        new_path = path.with_name(path.stem + path.suffix.lower())
        logger.debug('renaming "%s" to "%s"', path, new_path)
        os.rename(path, new_path)


@linterdex.register
class TestPermissionsOrphanExecutableBit(TestBase):
    """Test for files with an orphaned executable bit.

    An orphaned executable bit is an executable bit set without an according
    read bit set.
    """

    name = 'permissions-orphan-executable-bit'

    def _test(self, path, pathstat):
        """Run the test on path and stat object."""
        if bool(pathstat.st_mode & stat.S_IXUSR) and not bool(pathstat.st_mode & stat.S_IRUSR):
            return False
        elif bool(pathstat.st_mode & stat.S_IXGRP) and not bool(pathstat.st_mode & stat.S_IRGRP):
            return False
        elif bool(pathstat.st_mode & stat.S_IXOTH) and not bool(pathstat.st_mode & stat.S_IROTH):
            return False
        else:
            return True


@linterdex.register
class TestNameTempfile(TestBase):
    """Test if file seems to be a temporary file, based on its name."""

    name = 'name-tempfile'

    def __init__(self):  # noqa: D107
        super().__init__()
        self._regex = re.compile(r'^(core|.*~|dead.letter|,.*|.*\.v|.*\.emacs_[0-9]*|.*\.[Bb][Aa][Kk]|.*\.swp)$')

    def _test(self, path, pathstat):
        """Run the test on path and stat object."""
        if not stat.S_ISDIR(pathstat.st_mode) and self._regex.match(path.name):
            return False
        else:
            return True


@linterdex.register
class TestNameControlChars(TestBase):
    """Test if filename contains control characters."""

    name = 'name-controlchars'

    def __init__(self):  # noqa: D107
        super().__init__()

    def _test(self, path, pathstat):
        """Run the test on path and stat object."""
        if any(unicodedata.category(char)[0] == 'C' for char in path.name):
            return False
        else:
            return True

    def fix(self, path, pathstat):
        """Fix name by removing control chars from name."""
        new_path = path.with_name(''.join(ch for ch in path.name if unicodedata.category(ch)[0] != 'C'))
        logger.debug('renaming "%s" to "%s"', path, new_path)
        os.rename(path, new_path)


@linterdex.register
class TestNameSpaceAtStart(TestBase):
    """Test if filename starts with one or more spaces."""

    name = 'name-spaceatstart'

    def __init__(self):  # noqa: D107
        super().__init__()
        self._regex = re.compile(r'^ +(.*)$')  # spaces at start

    def _test(self, path, pathstat):
        """Run the test on path and stat object."""
        if self._regex.match(path.name):
            return False
        else:
            return True

    def fix(self, path, pathstat):
        """Remove space(s) at beginning of name."""
        result = self._regex.match(path.name)
        if result:
            new_path = path.with_name(result.group(1))
            logger.debug('renaming "%s" to "%s"', path, new_path)
            os.rename(path, new_path)


@linterdex.register
class TestNameSpaceAtEnd(TestBase):
    """Test if filename ends with one or more spaces."""

    name = 'name-spaceatend'

    def __init__(self):  # noqa: D107
        super().__init__()
        self._regex = re.compile(r'^(.*?) +$')  # spaces at end

    def _test(self, path, pathstat):
        """Run the test on path and stat object."""
        if self._regex.match(path.name):
            return False
        else:
            return True

    def fix(self, path, pathstat):
        """Remove space(s) at end of name."""
        result = self._regex.match(path.name)
        if result:
            new_path = path.with_name(result.group(1))
            logger.debug('renaming "%s" to "%s"', path, new_path)
            os.rename(path, new_path)


@linterdex.register
class TestNameSpaceDouble(TestBase):
    """Test if filename has two or more adjacent spaces in the name."""

    name = 'name-spacedouble'

    def __init__(self):  # noqa: D107
        super().__init__()
        self._regex = re.compile('  +')  # 2 or more adjacent spaces

    def _test(self, path, pathstat):
        """Run the test on path and stat object."""
        if self._regex.search(path.name):
            return False
        else:
            return True

    def fix(self, path, pathstat):
        """Replace adjacent space(s) with single space."""
        result = self._regex.sub(' ', path.name)
        if result:
            new_path = path.with_name(result)
            logger.debug('renaming "%s" to "%s"', path, new_path)
            os.rename(path, new_path)


@linterdex.register
class TestNameDangerous(TestBase):
    """Test if file has a dangerous name, in particular with regards to commands."""

    name = 'name-dangerous'

    def __init__(self):  # noqa: D107
        super().__init__()
        expressions = [
            r'^-.*',  # - at start of name
            r'.* -.*',  # - after space in name
        ]
        # TODO: test for shell meta characters?
        self._regex = re.compile(r'(%s)' % '|'.join(expressions))

    def _test(self, path, pathstat):
        """Run the test on path and stat object."""
        if self._regex.match(path.name):
            return False
        else:
            return True

    def experimentalfix(self, path, pathstat):
        """Fix dangerous names."""
        # definitely bogus implementation for now
        new_path = path.with_name(path.stem.strip().replace(' -', '-') + path.suffix)
        click.echo(new_path)
        logger.debug('renaming "%s" to "%s"', path, new_path)
        # os.rename(path, new_path)


@linterdex.register
class TestSizeZero(TestBase):
    """Test if file has 0 byte size."""

    name = 'size-zero'

    def __init__(self):  # noqa: D107
        super().__init__()
        # well known filenames that are 0 bytes by design
        self._allow_list = ('__init__.py', 'LOCK')
        self._allow_regex = re.compile(r'(?i).*\.lock|.*\.log|.*\.db-wal|.*\.sqlitedb-wal|.*\.sqlite-wal')

    def _test(self, path, pathstat):
        """Run the test on path and stat object."""
        def allow_name(name):
            if name in self._allow_list:
                return True
            if self._allow_regex.match(name):
                return True
            return False
        if pathstat.st_size == 0:
            # sockets are allowed to be 0 bytes:
            if stat.S_ISSOCK(pathstat.st_mode):
                return True
            if not allow_name(path.name):
                return False
        return True


@linterdex.register
class TestNameLength32(TestBase):
    """Test if filename is longer than 32 characters."""

    name = 'name-len32'

    def __init__(self):  # noqa: D107
        super().__init__()
        # stop words when fixing/shortening, ie remove these words entirely
        self._stopwords = ('pictures', 'picture', 'images', 'image', 'img')

    def _test(self, path, pathstat):
        """Run the test on path and stat object."""
        if len(path.name) > 32:
            return False
        else:
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


def colorize_differences_inline(a, b):
    """
    Highlight differences between strings a and b by creating a new string with custom highlighting.

    Example:
        ("filewithspeçialcharsüäö.txt", "filewithspecialcharsuao.txt")
        returns:
        "filewithspe{ç>c}ialchars{üäö>uao}.txt"
    """
    matcher = difflib.SequenceMatcher(None, a, b)

    def process_tag(tag, i1, i2, j1, j2):
        if tag == 'replace':
            return Style.DIM + '{' + Style.NORMAL + Fore.RED + matcher.a[i1:i2] + \
                Fore.RESET + Style.DIM + '>' + Style.NORMAL + Fore.GREEN + \
                matcher.b[j1:j2] + Fore.RESET + Style.DIM + '}' + Style.NORMAL
        elif tag == 'delete':
            return ''.join(
                (
                    Style.DIM, '{-', Style.NORMAL, Fore.RED, matcher.a[i1:i2],
                    Fore.RESET, Style.DIM, '}', Style.NORMAL
                )
            )
        elif tag == 'equal':
            return matcher.a[i1:i2]
        elif tag == 'insert':
            return Style.DIM + '{+' + Style.NORMAL + Fore.GREEN + \
                matcher.b[j1:j2] + Fore.RESET + Style.DIM + '}' + Style.NORMAL
        else:
            raise ValueError('Unknown tag %r' % tag)
    return ''.join(process_tag(*t) for t in matcher.get_opcodes())


def colorize_differences(a, b):
    """Highlight differences between strings a and b with ansi color codes."""
    matcher = difflib.SequenceMatcher(None, a, b)

    def process_tag_a(tag, i1, i2, j1, j2):
        if tag == 'replace':
            return Fore.RED + matcher.a[i1:i2] + Fore.RESET
        elif tag == 'delete':
            return Fore.RED + matcher.a[i1:i2] + Fore.RESET
        elif tag == 'equal':
            return matcher.a[i1:i2]
        elif tag == 'insert':
            return ''
        else:
            raise ValueError('Unknown tag %r' % tag)

    def process_tag_b(tag, i1, i2, j1, j2):
        if tag == 'replace':
            return Fore.GREEN + matcher.b[j1:j2] + Fore.RESET
        elif tag == 'delete':
            return Fore.GREEN + matcher.a[j1:j2] + Fore.RESET
        elif tag == 'equal':
            return matcher.a[i1:i2]
        elif tag == 'insert':
            return Fore.GREEN + matcher.b[j1:j2] + Fore.RESET
        else:
            raise ValueError('Unknown tag %r' % tag)
    a = ''.join(process_tag_a(*t) for t in matcher.get_opcodes())
    b = ''.join(process_tag_b(*t) for t in matcher.get_opcodes())
    return a, b


@linterdex.register
class TestNameNonAscii(TestBase):
    """Test if filename is encoded in non ascii."""

    name = 'name-non-ascii'

    def _test(self, path, pathstat):
        """Run the test on path and stat object."""
        if path.name != unidecode(path.name):
            # click.echo(colorize_differences_inline(a, b))
            # click.echo("%s -> %s" % (colorize_differences(a, b)))
            return False
        else:
            return True

    def experimentalfix(self, path, pathstat):
        """Attempt to transliterate non-ascii name to an ascii name."""
        from unidecode import unidecode
        newname = unidecode(path.name)
        if newname != path.name:
            newname = newname.replace('/', '_')  # unicode forward slash allowed, but not ascii!
            new_path = path.with_name(newname)
            logger.debug('renaming "%s" to "%s"', path, new_path)
            click.echo('renaming "%s" to "%s"' % (click.format_filename(path), new_path))
            # os.rename(path, new_path)


class FSLinter():
    """The main linter class."""

    def __init__(self):  # noqa: D107
        self.tests = []
        self._verbose = True
        self._fix = False
        self._experimental = False
        self._color = True

    def set_color(self, color):
        """Set the 'color' option."""
        self._color = color

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
        logger.debug('testing: %s', path)
        st = path.lstat()
        failures = [test for test in self.tests if not test(path, st)]
        if failures:
            click.secho(
                'FAIL[%s]:' % ','.join(sorted(test.name for test in failures)),
                nl=False,
                fg='red',
                bold=False,
                color=self._color
            )
            # https://click.palletsprojects.com/en/8.0.x/utils/#printing-filenames
            click.echo(click.format_filename(str(path)))
            if self._fix:
                for failure in failures:
                    if callable(getattr(failure, 'fix', None)):
                        logger.debug("Attempting to fix failure of '%s' for '%s'", failure.name, path)
                        failure.fix(path, st)
                    elif self._experimental and callable(getattr(failure, 'experimentalfix', None)):
                        logger.debug("Attempting to fix failure of '%s' for '%s'", failure.name, path)
                        failure.experimentalfix(path, st)
        else:
            if self._verbose:
                click.secho('OK:', nl=False, fg='green', bold=False, color=self._color)
                click.echo(click.format_filename(path))


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
                    # abspath = Path(os.path.join(root, relpath))
                    # click.echo(abspath.relative_to(start_path))
                    yield Path(os.path.join(root, relpath))
                files[:] = [f for f in files if not local_ignore_spec.match_file(f)]
                for relpath in files:
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
@click.option('-l', '--limit', multiple=True, help='Limit to given tests.')
@click.option('--list-tests', is_flag=True, default=False)
@click.option('-s', '--skip-test', multiple=True)
@click.option('--statistics', is_flag=True, default=False)
@click.option('--fix', is_flag=True, default=False)
@click.option('--color', default='auto', type=click.Choice(['auto', 'never', 'always'], case_sensitive=False))
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
    paths, skip_test, limit, list_tests, exclude, verbose, debug, hidden,
    skip_vcs_ignore, statistics, fix, experimental, color
):
    """Find paths that fail tests."""
    filetests = ClassRegistryInstanceCache(linterdex)
    linter = FSLinter()
    linter.set_verbose(verbose)
    linter.set_fix(fix)
    linter.set_experimental(experimental)
    if color.lower() == 'never':  # color: {auto,always,never}
        color = False
    else:
        color = True
    linter.set_color(color)

    if list_tests:
        for available_test in sorted(linterdex.keys()):
            click.secho('%s: ' % available_test, nl=False, bold=True, color=color)
            click.echo(filetests[available_test].__doc__)
        return 0
    if not paths:
        with click.Context(fs_lint, info_name='fs-lint') as ctx:
            click.echo(fs_lint.get_help(ctx))
            ctx.exit(1)
    if debug:
        logger.setLevel(logging.DEBUG)

    if not exclude:
        exclude = ()
    if not skip_vcs_ignore:
        # get global gitignore patterns
        try:
            gitexcludes = subprocess.check_output(  # noqa: S607
                'git config --path --get core.excludesfile 2>/dev/null',
                encoding='UTF-8',
                shell=True).strip()  # noqa: S602
        except subprocess.CalledProcessError:
            pass  # git may not be installed or no config may be present
        else:
            exclude += readlines(gitexcludes)
    if not hidden:
        exclude = ('.*',) + exclude  # assume .* matches most often and takes precedence
    ignore_spec = pathspec.PathSpec(map(pathspec.patterns.GitWildMatchPattern, exclude))

    for available_test in linterdex.keys():
        if limit:
            if available_test in limit:
                linter.register(filetests[available_test])
        elif available_test not in skip_test:
            linter.register(filetests[available_test])

    for path in walk_filesystem(paths, skip_vcs_ignore, exclude, ignore_spec):
        linter(path)

    if statistics:
        click.secho('Statistics', bold=True, color=color)
        for test in linter.tests:
            if test.count_failed() > 0:
                click.secho('%s: ' % test.name, nl=False, bold=False, color=color)
                click.secho('%i' % test.count_failed(), fg='red', nl=False, bold=False, color=color)
                click.secho('/%i' % (test.total - test.count_failed()), fg='green', bold=False, color=color)
            else:
                click.secho('%s: ' % test.name, nl=False, bold=False, color=color)
                click.secho('%i' % test.total, fg='green', bold=False, color=color)
    if any(test.count_failed() > 0 for test in linter.tests):
        sys.exit(1)
