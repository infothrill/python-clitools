# -*- coding: utf-8 -*-
"""Tests for the cli interface."""

import os
import shutil
import stat
import tarfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from clitools import fs_lint


@pytest.fixture
def change_test_dir(request):
    """Bla."""
    os.chdir(request.fspath.dirname)
    yield
    os.chdir(request.config.invocation_dir)


@pytest.fixture
def testfilesystem(tmp_path, request):
    """Generate a test filesystem."""
    tarball = os.path.join(request.fspath.dirname, 'resources', 'test-fs.tgz')
    os.chdir(tmp_path)
    tar = tarfile.open(tarball)
    tar.extractall()
    tar.close()
    yield tmp_path / 'test-fs'
    shutil.rmtree(tmp_path / 'test-fs')


def test_fs(testfilesystem):
    """Test cli run on example fs."""
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=str(testfilesystem)):
        result = runner.invoke(fs_lint.fs_lint, [
            '--color',
            'never',
            '--verbose',
            '--fix',
            '--experimental',
            '--statistics',
            str(testfilesystem)
        ]
        )
    assert 'FAIL' in result.output
    assert 42 == len(result.output.splitlines())
    assert 1 == result.exit_code


def test_empty_run():
    """Test empty cli run."""
    runner = CliRunner()
    result = runner.invoke(fs_lint.fs_lint)
    assert 'Usage' in result.output
    assert 1 == result.exit_code
    result = runner.invoke(fs_lint.fs_lint, ['--help'])
    assert 'Usage' in result.output
    assert 0 == result.exit_code
    result = runner.invoke(fs_lint.fs_lint, ['--list-tests'])
    assert 'Test if' in result.output
    assert 0 == result.exit_code


def test_testpermissionsworldwritable(tmp_path):
    """Test for TestPermissionsWorldWritable."""
    # setup test case
    test_path = tmp_path / 'testfile'
    test_path.touch()
    os.chmod(test_path, stat.S_IWOTH)

    # run test case
    test = fs_lint.TestPermissionsWorldWritable()
    assert test(test_path, test_path.lstat()) is False
    test.fix(test_path, test_path.lstat())
    assert test(test_path, test_path.lstat()) is True

    # cleanup
    test_path.unlink()


def test_testpermsworldreadable(tmp_path):
    """Test for TestPermissionsWorldReadable."""
    # setup test case
    test_path = tmp_path / 'testfile'
    test_path.touch()
    os.chmod(test_path, stat.S_IROTH)

    # run test case
    test = fs_lint.TestPermissionsWorldReadable()
    assert test(test_path, test_path.lstat()) is False
    test.fix(test_path, test_path.lstat())
    assert test(test_path, test_path.lstat()) is True

    # cleanup
    test_path.unlink()


def test_testpermsworldreadabledir(tmp_path):
    """Test for TestPermissionsWorldReadableDir."""
    # setup test case
    test_path = tmp_path / 'testdir'
    test_path.mkdir()
    test_path.chmod(0o755)

    # run test case
    test = fs_lint.TestPermissionsWorldReadableDir()
    assert test(test_path, test_path.lstat()) is False
    test.fix(test_path, test_path.lstat())
    assert test(test_path, test_path.lstat()) is True

    # cleanup
    test_path.rmdir()


@pytest.mark.parametrize(
    'name, perms, shouldpass',
    [
        ('orphanex', 0o661, False),
        ('orphanex', 0o616, False),
        ('orphanex', 0o166, False),
        ('okex', 0o766, True),
        ('okex', 0o756, True),
        ('okex', 0o757, True),
        ('okex', 0o566, True),
        ('okex', 0o656, True),
        ('okex', 0o665, True),
        ('noex', 0o644, True),
        ('noex', 0o464, True),
        ('noex', 0o446, True),
    ]
)
def test_testpermsorphanexecutablebit(tmp_path, name, perms, shouldpass):
    """Test for TestPermissionsOrphanExecutableBit."""
    # setup test case
    test_path = Path(tmp_path / name)
    test_path.touch()
    test_path.chmod(perms)

    # run test case
    test = fs_lint.TestPermissionsOrphanExecutableBit()
    assert test(test_path, test_path.lstat()) is shouldpass
    # TODO: fix
    # test.fix(test_path, test_path.lstat())
    # assert test(test_path, test_path.lstat()) is True

    # cleanup
    test_path.unlink()


@pytest.mark.parametrize(
    'bad, fixed, shouldpass',
    [
        ('testfile', 'testfile', True),
        ('test file', 'test file', True),
        ('testfile ', 'testfile ', True),
        (' testfile', 'testfile', False),
        ('  testfile', 'testfile', False),
        ('   testfile', 'testfile', False),
        ('   test file', 'test file', False),
    ]
)
def test_testnamespaceatstart(tmp_path, bad, fixed, shouldpass):
    """Test for TestNameSpaceAtStart."""
    # setup test case
    test_path = Path(tmp_path / bad)
    fixed_path = Path(tmp_path / fixed)
    test_path.touch()

    # run test case
    test = fs_lint.TestNameSpaceAtStart()
    assert test(test_path, test_path.lstat()) is shouldpass, 'Test should pass assertion'

    test.fix(test_path, test_path.lstat())
    assert shouldpass is test_path.exists(), 'Assert original file {0} was renamed according to expectation'.format(test_path)
    assert fixed_path.exists(), 'Assert new file after rename exists "{0}"->"{1}"'.format(test_path, fixed_path)
    assert test(fixed_path, fixed_path.lstat()) is True, 'Fixed file should pass test'

    # cleanup
    if test_path.exists():
        test_path.unlink()
    if fixed_path.exists():
        fixed_path.unlink()


@pytest.mark.parametrize(
    'bad, fixed, shouldpass',
    [
        ('testfile', 'testfile', True),
        ('test file', 'test file', True),
        (' testfile', ' testfile', True),
        ('testfile ', 'testfile', False),
        ('testfile  ', 'testfile', False),
        ('testfile   ', 'testfile', False),
        ('test file   ', 'test file', False),
    ]
)
def test_testnamespaceatend(tmp_path, bad, fixed, shouldpass):
    """Test for TestNameSpaceAtEnd."""
    # setup test case
    test_path = Path(tmp_path / bad)
    fixed_path = Path(tmp_path / fixed)
    test_path.touch()

    # run test case
    test = fs_lint.TestNameSpaceAtEnd()
    assert test(test_path, test_path.lstat()) is shouldpass, 'Test should pass assertion for "{0}"'.format(test_path)

    test.fix(test_path, test_path.lstat())
    assert shouldpass is test_path.exists(), 'Assert original file {0} was renamed according to expectation'.format(test_path)
    assert fixed_path.exists(), 'Assert new file after rename exists "{0}"->"{1}"'.format(test_path, fixed_path)
    assert test(fixed_path, fixed_path.lstat()) is True, 'Fixed file should pass test'

    # cleanup
    if test_path.exists():
        test_path.unlink()
    if fixed_path.exists():
        fixed_path.unlink()


@pytest.mark.parametrize(
    'bad, fixed, shouldpass',
    [
        ('testfile', 'testfile', True),
        ('test file', 'test file', True),
        (' testfile', ' testfile', True),
        ('testfile ', 'testfile ', True),
        ('testfile  ', 'testfile ', False),
        ('testfile   ', 'testfile ', False),
        ('test file   ', 'test file ', False),
        ('test  file   ', 'test file ', False),
        ('  test  file   ', ' test file ', False),
        ('test      file', 'test file', False),
    ]
)
def test_testnamespacedouble(tmp_path, bad, fixed, shouldpass):
    """Test for TestNameSpaceDouble."""
    # setup test case
    test_path = Path(tmp_path / bad)
    fixed_path = Path(tmp_path / fixed)
    test_path.touch()

    # run test case
    test = fs_lint.TestNameSpaceDouble()
    assert test(test_path, test_path.lstat()) is shouldpass, 'Test should pass assertion for "{0}"'.format(test_path)

    test.fix(test_path, test_path.lstat())
    assert shouldpass is test_path.exists(), 'Assert original file {0} was renamed according to expectation'.format(test_path)
    assert fixed_path.exists(), 'Assert new file after rename exists "{0}"->"{1}"'.format(test_path, fixed_path)
    assert test(fixed_path, fixed_path.lstat()) is True, 'Fixed file should pass test'

    # cleanup
    if test_path.exists():
        test_path.unlink()
    if fixed_path.exists():
        fixed_path.unlink()


@pytest.mark.parametrize(
    'bad, fixed, shouldpass',
    [
        ('testfile', 'testfile', True),
        ('test file', 'test file', True),
        ('test\tfile', 'testfile', False),
        ('testfile\x08', 'testfile', False),
    ]
)
def test_testnamecontrolchars(tmp_path, bad, fixed, shouldpass):
    """Test for TestNameControlChars."""
    # setup test case
    test_path = Path(tmp_path / bad)
    fixed_path = Path(tmp_path / fixed)
    test_path.touch()

    # run test case
    test = fs_lint.TestNameControlChars()
    assert test(test_path, test_path.lstat()) is shouldpass, 'Test should pass assertion'

    test.fix(test_path, test_path.lstat())
    assert shouldpass is test_path.exists(), 'Assert original file {0} was renamed according to expectation'.format(test_path)
    assert fixed_path.exists(), 'Assert new file after rename exists'
    assert test(fixed_path, fixed_path.lstat()) is True, 'Fixed file should pass test'

    # cleanup
    if test_path.exists():
        test_path.unlink()
    if fixed_path.exists():
        fixed_path.unlink()
