#!/usr/bin/env python

"""Setup the package."""

import sys

from setuptools import find_packages, setup

setup(
    name='clitools',
    version='0.2.1',
    url='https://github.com/infothrill/python-clitools',
    author='Paul Kremer',
    author_email='@'.join(('paul', 'spurious.biz')),  # avoid spam,
    description='Collection of CLI tools written in Python',
    packages=find_packages(),
    # https://packaging.python.org/tutorials/distributing-packages/#python-requires
    python_requires='>=3.7',
    setup_requires=['pytest-runner', 'setuptools>=12'],
    license='MIT',
    install_requires=[
        'click >= 6.7',
        'chardet >= 2.1',  # detectencoding
        'colorama',  # fs-lint
        'IPy >= 0.83',  # onlinepingheck
        'unidecode >= 0.04',  # transliterate
        'mutagen >= 1.39',  # mp3 tags
        'phx-class-registry >= 5.0',  # fs-lint
        'pathspec>=0.5.9',  # fs-lint
        'six',
        'python-gitlab',  # gitlab_shared_runners
        'python-slugify>=3.0.3',  # fs-lint
        'pyfzf>=0.3.1',  # note
        # the cli tool autocropscans depends on this to be in the PYTHONPATH,
        # since it is not packaged fully, it cannot be automatically be installed
        # https://github.com/msaavedra/autocrop
    ],
    tests_require=['pytest>=3.0.7'],
    entry_points={
        'console_scripts': [
            'detectencoding = clitools.detectencoding:main',
            'digssh = clitools.digssh:main',
            'fs-lint = clitools.fs_lint:fs_lint',
            'gitlab-shared-runners = clitools.gitlab_shared_runners:main',
            'id3v1toid3v2 = clitools.id3v1toid3v2:main',
            'autocropscans = clitools.autocropscans:main',
            'note = clitools.note:main',
            'onlinepingcheck = clitools.onlinepingcheck:main',
            'rdiff-backup-wrapper = clitools.rdiff_backup_wrapper:main',
            'rndpasswd = clitools.rndpasswd:main',
            'rot13 = clitools.rot13:main',
            'transliterate = clitools.transliterate:main',
            'tomp3 = clitools.tomp3:main',
        ]
    },
    package_data={'clitools/tests/resources': ['clitools/tests/resources/*.ini']},
    data_files=[],
    classifiers=[
        'DO NOT UPLOAD',  # block pypi publication
        'Topic :: Utilities',
        'Programming Language :: Python :: 3.7',
    ]
)
