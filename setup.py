#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Setup the package."""

from setuptools import setup, find_packages

import sys
if sys.version_info < (2, 7):
    sys.exit('Sorry, Python < 2.7 is not supported')

setup(
    name='clitools',
    version='0.2.1',
    url='https://github.com/infothrill/python-clitools',
    author='Paul Kremer',
    author_email='@'.join(('paul', 'spurious.biz')),  # avoid spam,
    description='Collection of CLI tools written in Python',
    packages=find_packages(),
    # https://packaging.python.org/tutorials/distributing-packages/#python-requires
    python_requires='>=3.5',
    setup_requires=['pytest-runner', 'setuptools>=12'],
    license='MIT',
    install_requires=[
        'click >= 6.7',
        'chardet >= 2.1',  # detectencoding
        'IPy >= 0.83',  # onlinepingheck
        'unidecode >= 0.04',  # transliterate
        'mutagen >= 1.39',  # mp3 tags
        'class-registry >= 2.1.2',  # fs-lint
        'six',
    ],
    tests_require=['pytest>=3.0.7'],
    entry_points={
        'console_scripts': [
            'detectencoding = clitools.detectencoding:main',
            'digssh = clitools.digssh:main',
            'fs-lint = clitools.fs_lint:main',
            'onlinepingcheck= clitools.onlinepingcheck:main',
            'rndpasswd = clitools.rndpasswd:main',
            'rot13 = clitools.rot13:main',
            'transliterate = clitools.transliterate:main',
            'tomp3 = clitools.tomp3:main',
        ]
    },
    data_files=[],
    classifiers=[
        'DO NOT UPLOAD',  # block pypi publication
        'Topic :: Utilities',
        'Programming Language :: Python :: 3.6',
    ]
)
