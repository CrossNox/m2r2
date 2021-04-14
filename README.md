M2R2
====

[![PyPI](https://img.shields.io/pypi/v/m2r2.svg)](https://pypi.python.org/pypi/m2r2)
[![PyPI version](https://img.shields.io/pypi/pyversions/m2r2.svg)](https://pypi.python.org/pypi/m2r2)
[![Documentation](https://img.shields.io/badge/docs-latest-brightgreen.svg)](https://crossnox.github.io/m2r2)
![Python package](https://github.com/CrossNox/m2r2/workflows/Python%20package/badge.svg)

--------------------------------------------------------------------------------

M2R2 converts a markdown file including reStructuredText (rst) markups to a valid
rst format.

## M2R: the original
M2R2 is a fork of [m2r](https://github.com/miyakogi/m2r) which hasn't been updated for a long time
and there's been no response from the author about a PR fixing a serious issue that broke several
pipelines using `sphinx3`. Every `m2r` config should work out of the box. I've changed some of the tooling for what I'm mostly using now. Below goes
the original readme, changing only what's needed to work with `m2r2`.

## Why another converter?

I wanted to write sphinx document in markdown, since it's widely used now and
easy to write code blocks and lists. However, converters using pandoc or
recommonmark do not support many rst markups and sphinx extensions. For
example, rst's reference link like ``see `ref`_`` (this is very convenient in
long document in which same link appears multiple times) will be converted to
a code block in HTML like `see <code>ref</code>_`, which is not expected.

## Features

* Basic markdown and some extensions (see below)
    * inline/block-level raw html
    * fenced-code block
    * tables
    * footnotes (``[^1]``)
* Inline- and Block-level rst markups
    * single- and multi-line directives (`.. directive::`)
    * inline-roles (``:code:`print(1)` ...``)
    * ref-link (``see `ref`_``)
    * footnotes (``[#fn]_``)
    * math extension inspired by [recommonmark](https://recommonmark.readthedocs.io/en/latest/index.html)
* Sphinx extension
    * add markdown support for sphinx
    * ``mdinclude`` directive to include markdown from md or rst files
    * option to parse relative links into ref and doc directives (``m2r_parse_relative_links``)
    * option to render ``mermaid`` blocks as graphs with [sphinxcontrib.mermaid](https://sphinxcontrib-mermaid-demo.readthedocs.io/en/latest/index.html`) (``m2r_use_mermaid``, default: auto)
* Pure python implementation
    * pandoc is not required

## Installation

Python 2.7 or Python 3.4+ is required.

```
pip install m2r2
```

Or

```
python3 -m pip install m2r2
```

or using `conda`

```
conda install -c conda-forge m2r2
```

## Usage

### Command Line

`m2r2` command converts markdown file to rst format.

```
m2r2 your_document.md [your_document2.md ...]
```

Then you will find `your_document.rst` in the same directory.

### Programmatic Use

Import `m2r2.convert` function and call it with markdown text.
Then it will return converted text.

```python
from m2r2 import convert
rst = convert('# Title\n\nSentence.')
print(rst)
# Title
# =====
#
# Sentence.
```

Or, use `parse_from_file` function to load markdown file and obtain converted
text.

```python
from m2r2 import parse_from_file
output = parse_from_file('markdown_file.md')
```

This is an example of setup.py to write README in markdown, and publish it to
PyPI as rst format.

```python
readme_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'README.md')
try:
    from m2r2 import parse_from_file
    readme = parse_from_file(readme_file)
except ImportError:
    # m2r2 may not be installed in user environment
    with open(readme_file) as f:
        readme = f.read()
setup(
    ...,
    long_description=readme,
    ...,
)
```

### Sphinx Integration

In your conf.py, add the following lines.

```python
extensions = [
    ...,
    'm2r2',
]

# source_suffix = '.rst'
source_suffix = ['.rst', '.md']
```

Write index.md and run `make html`.

When `m2r2` extension is enabled on sphinx and `.md` file is loaded, m2r2
converts to rst and pass to sphinx, not making new `.rst` file.

#### mdinclude directive

Like `.. include:: file` directive, `.. mdinclude:: file` directive inserts
markdown file at the line.

Note: do not use `.. include:: file` directive to include markdown file even if
in the markdown file, please use `.. mdinclude:: file` instead.

## Restrictions

* In the rst's directives, markdown is not available. Please write in rst.
* Column alignment of tables is not supported. (rst does not support this feature)
* Heading with overline-and-underline is not supported.
  * Heading with underline is OK
* Rst heading marks are currently hard-coded and unchangeable.
  * H1: `=`, H2: `-`, H3: `^`, H4: `~`, H5: `"`, H6: `#`

If you find any bug or unexpected behaviour, please report it to
[Issues](https://github.com/crossnox/m2r2/issues).

## Example

See [example document](https://crossnox.github.io/m2r2/example.html) and [its
source code](https://github.com/crossnox/m2r2/blob/master/docs/example.md).

*Note from the original author:* I'm using m2r for writing user guide of [WDOM](https://github.com/miyakogi/wdom).
So you can see it as another example. Its [HTML is
here](http://wdom-py.readthedocs.io/en/latest/guide/index.html), and [its
source code is here](https://github.com/miyakogi/wdom/tree/dev/docs/guide).

### Demo editor

*Note:* This hasn't received any updates.

Demo editor of m2r is available.
If you are interested in m2r, please try it.

[https://github.com/miyakogi/m2rdemo](https://github.com/miyakogi/m2rdemo)

## Dev install
Please install the `dev` dependencies and `pre-commit` hooks with:
```bash
pip install -r requirements-dev.txt
pre-commit install
```

## Acknowledgement

m2r is written as an extension of
[mistune](http://mistune.readthedocs.io/en/latest/), which is highly extensible
pure-python markdown parser.
Without the mistune, I couldn't write this. Thank you!

## Licence

[MIT](https://github.com/crossnox/m2r2/blob/master/LICENSE)
