# -*- coding: utf-8 -*-
"""Tests for the cli interface."""

from __future__ import absolute_import

import unittest

from click.testing import CliRunner

from clitools.rndpasswd import main


class CliTestCase(unittest.TestCase):
    """Test cases for the api methods."""

    # pylint: disable=no-self-use
    def test_empty_run(self):
        """Test empty cli run."""
        runner = CliRunner()
        result = runner.invoke(main)
        self.assertTrue(len(result.output) > 8)
        self.assertEqual(0, result.exit_code)
