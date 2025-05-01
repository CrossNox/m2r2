#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Setup code"""

from os import path

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup  # type: ignore # pylint: disable=deprecated-module

readme_file = path.join(path.dirname(path.abspath(__file__)), "README.md")
with open(readme_file) as f:
    readme = f.read()


__version__ = "0.3.4"

install_requires = ["mistune==0.8.4", "docutils>=0.19"]
test_requirements = ["pygments"]

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
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Text Processing",
    ],
    install_requires=install_requires,
    test_suite="tests",
    tests_require=test_requirements,
    python_requires=">=3.7",
)
