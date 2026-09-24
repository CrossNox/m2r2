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
    * option to parse relative document links into ``:doc:`` roles (``m2r_parse_relative_links``)
    * resolve links to Markdown headings by GitHub anchor and to RST labels
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

Import `m2r2.convert` function and call it with markdown text. Then it will return converted text.

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

### Upgrading to 2.0

#### Update Python calls

Replace `disable_inline_math=True` with `inline_math=None` in calls to `convert`, `parse_from_file`, and `M2R2`:

```python
# 1.x
convert(markdown, disable_inline_math=True)

# 2.0
convert(markdown, inline_math=None)
```

Remove `disable_inline_math=False` wherever you set it. The default remains `"legacy"`. To parse `$x$` instead of the legacy `` `$x$` `` form, pass `inline_math="dollar"`. The CLI still accepts `--disable-inline-math`. Use `--inline-math dollar` to select dollar delimiters there.

If you passed a `RestRenderer` to `M2R2` only to set its options, pass those options to `M2R2` instead. The `plugins` argument still works:

```python
# 1.x
M2R2(renderer=RestRenderer(parse_relative_links=True), plugins=plugins)

# 2.0
M2R2(parse_relative_links=True, plugins=plugins)
```

Do the same for `anonymous_references` and `use_mermaid`. If you used `RestRenderer` directly with Mistune, switch to `M2R2` to obtain a complete RST document. Direct rendering now omits the required role and substitution definitions.

For a custom Sphinx parser or directive, construct the converter from the current docutils document:

```python
from m2r2.sphinx.converter import SphinxM2R2

rst = SphinxM2R2(document, source_path=markdown_path)(markdown)
```

#### Update Sphinx configuration

In `conf.py`, replace `m2r_disable_inline_math = True` with `m2r_inline_math = None`. Remove `m2r_disable_inline_math = False` to keep the default legacy syntax. To select dollar delimiters, set `m2r_inline_math = "dollar"`. The old name still works but emits a deprecation warning.

#### Review Markdown and generated RST

Build your Sphinx project and check fragment links. Links to Markdown headings now use GitHub heading slugs, such as `#installation` or `#installation-1` for a repeated heading. Explicit RST labels still resolve. Set `m2r_parse_relative_links = True` in `conf.py` if you link to a heading in another Markdown file, such as `[Install](guide.md#installation)`. Fix any `m2r2.anchor` warnings by correcting the document path or fragment.

A leading `/` in `.. mdinclude:: /part.md` now points to `part.md` in the Sphinx source directory. For a file outside that directory, use a path relative to the file containing the directive. Check image paths in included Markdown too. They now resolve from the included file's directory.

Remove any `:parser:` option from `mdinclude`. The directive always parses Markdown. If a link uses a Markdown title such as `[Guide](guide.md "extra")`, move important title text into the visible link text or nearby prose. RST output does not retain link titles.

If you keep generated RST or snapshots in your repository, regenerate them. Generated substitution names have changed. Avoid referencing those names from handwritten RST.

### Inline math

Choose the syntax with `inline_math` in Python, `m2r_inline_math` in Sphinx, or `--inline-math` on the command line:

| Mode | Syntax |
| --- | --- |
| `"legacy"` (default) | `` `$x^2$` `` |
| `"dollar"` | `$x^2$` or `` $`x^2`$ `` |
| `None` (CLI: `--disable-inline-math`) | Disable inline math conversion |

For example:

```python
convert("An equation: $x^2$.", inline_math="dollar")
```

In `conf.py`, set `m2r_inline_math = "dollar"` to use the same inline math delimiters as GitHub and GitLab. Ordinary code spans remain code in this mode.

Bare `$...$` delimiters must enclose nonempty text on one line without spaces at its edges. A closing dollar sign cannot be followed by a digit. These rules keep examples such as `$5-$10` and `$20,000 and $30,000` as text. Escape literal dollar signs with a backslash when they could be interpreted as delimiters. Backslashes inside math expressions, including `\$`, are preserved.

`None` disables only inline math. Fenced `math` blocks still render as math. Double-dollar display math is not supported. Use a fenced `math` block instead.

### GitHub alerts

GitHub alerts become RST admonitions automatically:

```markdown
> [!WARNING]
> Back up your **files** before proceeding.
```

This produces:

```rst
.. warning::

   Back up your **files** before proceeding.
```

Supported markers are `[!NOTE]`, `[!TIP]`, `[!IMPORTANT]`, `[!WARNING]`, and `[!CAUTION]`. Put the marker on its own first line in a top-level block quote. The body supports Markdown formatting, including paragraphs, lists, and code blocks. Alerts nested inside lists or other quotes remain ordinary quotes. Emoji shortcodes such as `:warning:` do not create admonitions.

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

#### Links to headings and labels

Under Sphinx, a link such as `[install](#installation)` resolves the anchor that GitHub gives the heading. Repeated headings use numbered anchors such as `#installation-1`. A fragment can also name an explicit RST label.

Enable `m2r_parse_relative_links` to resolve links to anchors in other Markdown documents:

```python
m2r_parse_relative_links = True
```

Then `[install](guide.md#installation)` resolves within `guide.md`. Relative links without a fragment become ``:doc:`` roles. A missing document or anchor produces an `m2r2.anchor` warning. Suppress these warnings in `conf.py` only when unresolved links are intentional:

```python
suppress_warnings = ["m2r2.anchor"]
```

#### mdinclude directive

Use `mdinclude` in a Markdown or RST document to convert and insert another Markdown file:

```rst
.. mdinclude:: path/to/part.md
```

A relative path starts at the file holding the directive. A path beginning with `/` starts at the Sphinx source directory.

Relative Markdown image paths, such as `![Badge](assets/badge.svg)`, start at the included Markdown file's directory. This also applies to inline images, tables, and nested includes. For example, a project-root `README.md` included from `docs/index.rst` can use images from `assets/` beside the README without symlinks. Image paths beginning with `/` start at the Sphinx source directory.

The directive accepts these options:

* `start-line` is zero-based and `end-line` is exclusive. For example, `:start-line: 1` with `:end-line: 3` keeps the second and third lines.
* `lines` selects one-based lines and ranges such as `1, 3-5, 8-`. It cannot be combined with `start-line`, `end-line`, `literal`, or `code`.
* `start-after` and `end-before` keep the text between two markers. Like docutils' `include`, each marker matches text rather than a whole line, and the marker itself is omitted. Line selection happens before marker matching.
* `encoding` sets the source file encoding. `tab-width` sets the tab width.
* `literal` shows the file without converting it. `code` also skips conversion and uses its value as the syntax language.
* With `literal` or `code`, `number-lines` adds line numbers, `name` gives the shown block a target name, and `class` adds CSS classes.

The `parser` option is not supported because `mdinclude` always parses Markdown. Docutils reports it as an unknown option. Use `mdinclude`, not `include`, for a Markdown file that should be converted.

#### Using mdinclude with another markdown parser

The `m2r2` extension parses `.md` files, so Sphinx refuses to load it next to another extension that does the same, such as myst-parser. To keep the other parser for `.md` files and still use `mdinclude`, enable `m2r2.mdinclude` instead. It adds the `mdinclude` directive and the `m2r_*` config values, but no parser.

```python
extensions = [
    "myst_parser",
    "m2r2.mdinclude",
]
```

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
