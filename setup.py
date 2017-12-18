#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Setup the package."""

from setuptools import setup, find_packages


setup(
    name='clitools',
    version='0.1.0',
    url='https://github.com/infothrill/python-clitools',
    author='Paul Kremer',
    author_email='@'.join(("paul", "spurious.biz")),  # avoid spam,
    description='Collection of CLI tools written in Python',
    packages=find_packages(),
    license='MIT',
    install_requires=[
        'click >= 6.7',
        'chardet >= 2.1', # detectencoding
        'IPy >= 0.83', # onlinepingheck
        'unidecode >= 0.04',  # transliterate
        'mutagen >= 1.39', # mp3 tags
        'six',
        ],
    setup_requires=['pytest-runner'],
    tests_require=['pytest>=3.0.7'],
    entry_points={
        "console_scripts": [
            "detectencoding = clitools.detectencoding:main",
            "digssh = clitools.digssh:main",
            "onlinepingcheck= clitools.onlinepingcheck:main",
            "rndpasswd = clitools.rndpasswd:main",
            "rot13 = clitools.rot13:main",
            "transliterate = clitools.transliterate:main",
            "tomp3 = clitools.tomp3:main",
        ]
    },
    data_files=[],
)
