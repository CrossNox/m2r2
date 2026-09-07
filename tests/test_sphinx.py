"""Sphinx integration tests for m2r2.

Tests the Sphinx extension setup(), M2R2Parser, and MdInclude directive
using real Sphinx builds in temporary directories.
"""

import shutil
import tempfile
import warnings
from io import StringIO
from pathlib import Path
from unittest import TestCase

from sphinx.testing.util import SphinxTestApp


def _build(conf="", files=None):
    """Build a Sphinx project and return (app, tmpdir, outdir, warnings).

    Args:
        conf: Extra lines appended to conf.py (m2r2 is always loaded).
        files: Dict of {filename: content} to write into srcdir.

    Returns:
        Tuple of (SphinxTestApp, tmpdir path, outdir Path, warning string).
        Caller must clean up tmpdir via shutil.rmtree.
    """
    if files is None:
        files = {}

    tmpdir = tempfile.mkdtemp()
    srcdir = Path(tmpdir) / "src"
    srcdir.mkdir()

    conf_text = f"""\
extensions = ["m2r2"]
{conf}
"""
    (srcdir / "conf.py").write_text(conf_text)

    for name, content in files.items():
        (srcdir / name).write_text(content)

    status = StringIO()
    warning = StringIO()
    app = SphinxTestApp(
        buildername="html",
        srcdir=srcdir,
        freshenv=True,
        status=status,
        warning=warning,
    )
    app.build()
    return app, tmpdir, Path(app.outdir), warning.getvalue()


class SphinxTestBase(TestCase):
    """Base class that manages Sphinx app and tmpdir cleanup."""

    def build(self, conf="", files=None):
        app, tmpdir, outdir, warnings = _build(conf=conf, files=files)
        self.addCleanup(app.cleanup)
        self.addCleanup(shutil.rmtree, tmpdir, ignore_errors=True)
        return app, outdir, warnings


class TestSetup(SphinxTestBase):
    """Test the Sphinx extension setup() function."""

    def test_config_defaults_registered(self):
        app, _, _ = self.build(files={"index.md": "# Hello\n"})
        self.assertFalse(app.config.m2r_no_underscore_emphasis)
        self.assertFalse(app.config.m2r_parse_relative_links)
        self.assertFalse(app.config.m2r_anonymous_references)
        self.assertFalse(app.config.m2r_disable_inline_math)
        self.assertFalse(app.config.m2r_use_mermaid)

    def test_md_source_suffix_registered(self):
        app, _, _ = self.build(files={"index.md": "# Hello\n"})
        self.assertIn(".md", app.config.source_suffix)

    def test_setup_return_value(self):
        """Verify setup() returns proper extension metadata."""
        from m2r2 import __version__

        app, _, _ = self.build(files={"index.md": "# Hello\n"})
        # Sphinx unpacks the metadata dict into Extension attributes
        ext = app.extensions.get("m2r2")
        self.assertIsNotNone(ext)
        self.assertEqual(ext.version, __version__)
        self.assertTrue(ext.parallel_read_safe)
        self.assertTrue(ext.parallel_write_safe)

    def test_mermaid_auto_detect(self):
        """m2r_use_mermaid defaults to True when sphinxcontrib.mermaid is loaded."""
        app, _, _ = self.build(files={"index.md": "# Hello\n"})
        self.assertFalse(app.config.m2r_use_mermaid)

    def test_deprecated_no_underscore_emphasis(self):
        """Old 'no_underscore_emphasis' config emits deprecation and still works."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _, outdir, _ = self.build(
                conf="no_underscore_emphasis = True",
                files={
                    "index.md": """\
# Test

_underscored_ text
"""
                },
            )
        deprecation_msgs = [x for x in w if issubclass(x.category, DeprecationWarning)]
        self.assertTrue(
            any("no_underscore_emphasis" in str(m.message) for m in deprecation_msgs),
        )
        html = (outdir / "index.html").read_text()
        self.assertIn("_underscored_", html)

    def test_explicit_new_config_takes_precedence(self):
        """Honor an explicit False even when the deprecated option is True."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            _, outdir, _ = self.build(
                conf="""\
no_underscore_emphasis = True
m2r_no_underscore_emphasis = False""",
                files={
                    "index.md": """\
# Test

_underscored_ text
"""
                },
            )
        self.assertIn("<em>underscored</em>", (outdir / "index.html").read_text())


class TestM2R2Parser(SphinxTestBase):
    """Test M2R2Parser as a Sphinx source parser."""

    def test_basic_markdown_build(self):
        _, outdir, _ = self.build(
            files={
                "index.md": """\
# Hello World

A paragraph.
"""
            }
        )
        html = (outdir / "index.html").read_text()
        self.assertIn("Hello World", html)
        self.assertIn("A paragraph", html)

    def test_no_underscore_emphasis_config(self):
        _, outdir, _ = self.build(
            conf="m2r_no_underscore_emphasis = True",
            files={
                "index.md": """\
# Test

_underscored_ text
"""
            },
        )
        html = (outdir / "index.html").read_text()
        self.assertIn("_underscored_", html)

    def test_anonymous_references_config(self):
        _, outdir, _ = self.build(
            conf="m2r_anonymous_references = True",
            files={
                "index.md": """\
# Test

[link](http://example.com)
"""
            },
        )
        html = (outdir / "index.html").read_text()
        self.assertIn("http://example.com", html)

    def test_inline_html_renders(self):
        _, outdir, _ = self.build(
            files={
                "index.md": """\
# Test

text <b>bold</b> text
"""
            }
        )
        html = (outdir / "index.html").read_text()
        self.assertIn("<b>bold</b>", html)

    def test_code_block(self):
        _, outdir, _ = self.build(
            files={
                "index.md": """\
# Test

```python
print('hello')
```
"""
            }
        )
        html = (outdir / "index.html").read_text()
        self.assertIn("print", html)

    def test_multiple_documents(self):
        """Ensure converter state doesn't leak between documents."""
        _, outdir, _ = self.build(
            files={
                "index.md": (
                    """\
# Index

text <b>bold</b> text

```{toctree}
doc2
```
"""
                ),
                "doc2.md": """\
# Doc 2

Plain text only.
""",
            }
        )
        html1 = (outdir / "index.html").read_text()
        html2 = (outdir / "doc2.html").read_text()
        self.assertIn("<b>bold</b>", html1)
        self.assertIn("Plain text only", html2)
        # raw-html-m2r role should NOT appear in doc2 (no HTML there)
        self.assertNotIn("raw-html-m2r", html2)


class TestMdInclude(SphinxTestBase):
    """Test the mdinclude directive."""

    def test_repeated_image_in_included_tables(self):
        """Render repeated image substitutions across included documents."""
        table = """\
| A | B |
|---|---|
| before ![A](https://example.com/a.png) after | B |
"""
        _, outdir, build_warnings = self.build(
            files={
                "index.rst": """\
Test
====

.. mdinclude:: first.txt

.. mdinclude:: second.txt

.. mdinclude:: first.txt
""",
                "first.txt": table,
                "second.txt": table,
            }
        )
        self.assertEqual(build_warnings, "")
        html = (outdir / "index.html").read_text()
        self.assertEqual(html.count('src="https://example.com/a.png"'), 3)

    def test_image_shared_by_markdown_source_and_include(self):
        """Reuse image definitions from the including Markdown document."""
        image = "before ![A](https://example.com/a.png) after\n"
        _, outdir, build_warnings = self.build(
            files={
                "index.md": """\
# Test

.. mdinclude:: image.txt

"""
                + image,
                "image.txt": image,
            }
        )
        self.assertEqual(build_warnings, "")
        html = (outdir / "index.html").read_text()
        self.assertEqual(html.count('src="https://example.com/a.png"'), 2)

    def test_basic_include(self):
        _, outdir, _ = self.build(
            files={
                "index.rst": """\
Test
====

.. mdinclude:: included.md
""",
                "included.md": """\
## Included Section

Included content.
""",
            }
        )
        html = (outdir / "index.html").read_text()
        self.assertIn("Included Section", html)
        self.assertIn("Included content", html)

    def test_start_line_zero(self):
        """Regression: start-line=0 must not be treated as falsy."""
        _, outdir, _ = self.build(
            files={
                "index.rst": (
                    """\
Test
====

.. mdinclude:: included.md
   :start-line: 0
   :end-line: 2
"""
                ),
                "included.md": """\
line0

line2

line4
""",
            }
        )
        html = (outdir / "index.html").read_text()
        self.assertIn("line0", html)
        self.assertNotIn("line4", html)

    def test_end_line_only(self):
        _, outdir, _ = self.build(
            files={
                "index.rst": (
                    """\
Test
====

.. mdinclude:: included.md
   :end-line: 1
"""
                ),
                "included.md": """\
first

second
""",
            }
        )
        html = (outdir / "index.html").read_text()
        self.assertIn("first", html)
        self.assertNotIn("second", html)

    def test_start_line_only(self):
        _, outdir, _ = self.build(
            files={
                "index.rst": (
                    """\
Test
====

.. mdinclude:: included.md
   :start-line: 2
"""
                ),
                "included.md": """\
first

second
""",
            }
        )
        html = (outdir / "index.html").read_text()
        self.assertNotIn("first", html)
        self.assertIn("second", html)

    def test_include_with_config_options(self):
        """mdinclude should respect Sphinx m2r2 config."""
        _, outdir, _ = self.build(
            conf="m2r_no_underscore_emphasis = True",
            files={
                "index.rst": """\
Test
====

.. mdinclude:: included.md
""",
                "included.md": "_underscored_\n",
            },
        )
        html = (outdir / "index.html").read_text()
        self.assertIn("_underscored_", html)
