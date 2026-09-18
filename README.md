# M2R2

[![PyPI](https://img.shields.io/pypi/v/m2r2.svg)](https://pypi.python.org/pypi/m2r2)
[![PyPI version](https://img.shields.io/pypi/pyversions/m2r2.svg)](https://pypi.python.org/pypi/m2r2)
[![Documentation](https://img.shields.io/badge/docs-latest-brightgreen.svg)](https://crossnox.github.io/m2r2)
![Tests](https://github.com/CrossNox/m2r2/actions/workflows/tests.yml/badge.svg)

---

M2R2 converts a markdown file including reStructuredText (rst) markups to a valid rst format.

## M2R: the original

M2R2 is a fork of [m2r](https://github.com/miyakogi/m2r) which has been archived. Every `m2r` config should work out of the box.

## Why another converter?

Sphinx documents benefit from being written in markdown, since it's widely used and easy to write code blocks and lists. However, converters using pandoc or recommonmark do not support many rst markups and sphinx extensions. For example, rst's reference link like ``see `ref`_`` (very convenient in long documents where the same link appears multiple times) gets converted to a code block in HTML like `see <code>ref</code>_`, which is not expected.

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
    * option to render ``mermaid`` blocks as graphs with [sphinxcontrib.mermaid](https://sphinxcontrib-mermaid-demo.readthedocs.io/en/latest/index.html) (``m2r_use_mermaid``, default: auto)
      * auto means that m2r2 will check if `sphinxcontrib.mermaid` has been added to the extensions list
* Pure python implementation
    * pandoc is not required

## Installation

Python 3.9+ is required.

```bash
uv add m2r2
```

Or use [uvx](https://docs.astral.sh/uv/guides/tools/) to run without installing:

```bash
uvx m2r2 your_document.md
```

For Sphinx integration:

```bash
uv add m2r2[sphinx]
```

## Usage

### Command Line

`m2r2` command converts markdown file to rst format.

```bash
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

Or, use `parse_from_file` function to load a markdown file and obtain converted text.

```python
from m2r2 import parse_from_file

output = parse_from_file('markdown_file.md')
```

### Upgrading to 1.0

The reusable converter class is named `M2R2`. Existing imports of `M2R` still
work through an alias. The `convert` and `parse_from_file` functions remain available.

Generated RST may use different spacing while preserving document content and
structure. Standalone images keep block image directives. Images within text,
headings, and table cells use substitutions so they can appear inline.
RST cannot nest inline markup, so emphasis is applied to surrounding text
while nested links and code retain their own formatting.

In Sphinx configuration, use `m2r_no_underscore_emphasis` instead of
`no_underscore_emphasis`. The old name still works with a deprecation warning.

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

When `m2r2` extension is enabled on sphinx and `.md` file is loaded, m2r2 converts to rst and pass to sphinx, not making new `.rst` file.

#### mdinclude directive

Like `.. include:: file` directive, `.. mdinclude:: file` directive inserts markdown file at the line.

Note: do not use `.. include:: file` directive to include markdown file even if in the markdown file, please use `.. mdinclude:: file` instead.

## Restrictions

* In the rst's directives, markdown is not available. Please write in rst.
* Column alignment of tables is not supported. (rst does not support this feature)
* Heading with overline-and-underline is not supported.
  * Heading with underline is OK
* Rst heading marks are currently hard-coded and unchangeable.
  * H1: `=`, H2: `-`, H3: `^`, H4: `~`, H5: `"`, H6: `#`

If you find any bug or unexpected behaviour, please report it to [Issues](https://github.com/crossnox/m2r2/issues).

## Example

See [example document](https://crossnox.github.io/m2r2/example.html) and [its source code](https://github.com/crossnox/m2r2/blob/master/docs/example.md).

## Contributing

See [CONTRIBUTING.md](https://github.com/CrossNox/m2r2/blob/master/CONTRIBUTING.md) for development setup and guidelines.

## Acknowledgement

m2r2 is written as an extension of [mistune](https://mistune.readthedocs.io/), which is a highly extensible pure-python markdown parser. Without mistune, this project wouldn't exist. Thank you!

## Licence

[MIT](https://github.com/crossnox/m2r2/blob/master/LICENSE)
