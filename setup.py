#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
from os import path

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

readme_file = path.join(path.dirname(path.abspath(__file__)), "README.md")
try:
    from m2r2 import parse_from_file

    readme = parse_from_file(readme_file)
except ImportError:
    with open(readme_file) as f:
        readme = f.read()


__version__ = "0.2.6"

install_requires = ["mistune", "docutils"]
test_requirements = ["pygments"]
if sys.version_info < (3, 3):
    test_requirements.append("mock")

setup(
    name="m2r2",
    version=__version__,
    description="Markdown and reStructuredText in a single file.",
    long_description=readme,
    long_description_content_type="text/markdown",
    author="Hiroyuki Takagi",
    author_email="miyako.dev@gmail.com",
    maintainer="CrossNox",
    maintainer_email="ijmermet+m2r2@gmail.com",
    url="https://github.com/crossnox/m2r2",
    py_modules=["m2r2"],
    entry_points={"console_scripts": "m2r2 = m2r2:main"},
    include_package_data=True,
    license="MIT",
    zip_safe=False,
    keywords="Markdown reStructuredText sphinx-extension",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Framework :: Sphinx :: Extension",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Topic :: Text Processing",
    ],
    install_requires=install_requires,
    test_suite="tests",
    tests_require=test_requirements,
)
