# -*- coding: utf-8 -*-
"""Tests for the cli interface."""

import pytest
import shutil
import os
import stat
import tarfile

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
        result = runner.invoke(fs_lint.fs_lint, [str(testfilesystem)])
    assert 'FAIL' in result.output
    assert 1 == result.exit_code


def test_empty_run():
    """Test empty cli run."""
    runner = CliRunner()
    result = runner.invoke(fs_lint.fs_lint)
    assert 'Usage' in result.output
    assert 1 == result.exit_code


def test_TestPermissionsWorldWritable(tmp_path):
    """Test for TestPermissionsWorldWritable."""
    test_path = tmp_path / 'testfile'
    with open(test_path, 'x') as _:
        pass
    os.chmod(test_path, stat.S_IWOTH)
    test = fs_lint.TestPermissionsWorldWritable()
    assert test.count_failed() == 0
    test(test_path, test_path.lstat())
    assert test.count_failed() == 1

    test.fix(test_path, test_path.lstat())
    test = fs_lint.TestPermissionsWorldWritable()
    test(test_path, test_path.lstat())
    assert test.count_failed() == 0

    os.unlink(test_path)
