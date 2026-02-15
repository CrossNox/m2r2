#!/usr/bin/env python3
"""Sphinx integration tests for m2r2.

Tests the Sphinx extension setup(), M2R2Parser, and MdInclude directive
using real Sphinx builds in temporary directories.
"""

import tempfile
from io import StringIO
from pathlib import Path
from unittest import TestCase

from sphinx.testing.util import SphinxTestApp


def _build(conf="", files=None, *, srcdir_name="src"):
    """Build a Sphinx project and return (app, outdir, warnings).

    Args:
        conf: Extra lines appended to conf.py (m2r2 is always loaded).
        files: Dict of {filename: content} to write into srcdir.
        srcdir_name: Subdirectory name for the source tree.

    Returns:
        Tuple of (SphinxTestApp, outdir Path, warning string).
    """
    if files is None:
        files = {}

    tmpdir = tempfile.mkdtemp()
    srcdir = Path(tmpdir) / srcdir_name
    srcdir.mkdir()

    conf_text = f'extensions = ["m2r2"]\n{conf}\n'
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
    return app, Path(app.outdir), warning.getvalue()


class TestSetup(TestCase):
    """Test the Sphinx extension setup() function."""

    def test_config_defaults_registered(self):
        app, _, _ = _build(files={"index.md": "# Hello\n"})
        try:
            self.assertFalse(app.config.no_underscore_emphasis)
            self.assertFalse(app.config.m2r_parse_relative_links)
            self.assertFalse(app.config.m2r_anonymous_references)
            self.assertFalse(app.config.m2r_disable_inline_math)
            self.assertFalse(app.config.m2r_use_mermaid)
        finally:
            app.cleanup()

    def test_md_source_suffix_registered(self):
        app, _, _ = _build(files={"index.md": "# Hello\n"})
        try:
            self.assertIn(".md", app.config.source_suffix)
        finally:
            app.cleanup()

    def test_setup_return_value(self):
        """Verify setup() returns proper extension metadata."""
        from m2r2 import __version__

        app, _, _ = _build(files={"index.md": "# Hello\n"})
        try:
            # Sphinx unpacks the metadata dict into Extension attributes
            ext = app.extensions.get("m2r2")
            self.assertIsNotNone(ext)
            self.assertEqual(ext.version, __version__)
            self.assertTrue(ext.parallel_read_safe)
            self.assertTrue(ext.parallel_write_safe)
        finally:
            app.cleanup()

    def test_mermaid_auto_detect(self):
        """m2r_use_mermaid defaults to True when sphinxcontrib.mermaid is loaded."""
        # Without mermaid extension
        app1, _, _ = _build(files={"index.md": "# Hello\n"})
        try:
            self.assertFalse(app1.config.m2r_use_mermaid)
        finally:
            app1.cleanup()


class TestM2R2Parser(TestCase):
    """Test M2R2Parser as a Sphinx source parser."""

    def test_basic_markdown_build(self):
        app, outdir, _ = _build(
            files={
                "index.md": "# Hello World\n\nA paragraph.\n",
            }
        )
        try:
            html = (outdir / "index.html").read_text()
            self.assertIn("Hello World", html)
            self.assertIn("A paragraph", html)
        finally:
            app.cleanup()

    def test_no_underscore_emphasis_config(self):
        app, outdir, _ = _build(
            conf="no_underscore_emphasis = True",
            files={"index.md": "# Test\n\n_underscored_ text\n"},
        )
        try:
            html = (outdir / "index.html").read_text()
            # With no_underscore_emphasis, _underscored_ is kept as-is
            self.assertIn("_underscored_", html)
        finally:
            app.cleanup()

    def test_anonymous_references_config(self):
        app, outdir, _ = _build(
            conf="m2r_anonymous_references = True",
            files={"index.md": "# Test\n\n[link](http://example.com)\n"},
        )
        try:
            html = (outdir / "index.html").read_text()
            self.assertIn("http://example.com", html)
        finally:
            app.cleanup()

    def test_inline_html_renders(self):
        app, outdir, _ = _build(
            files={
                "index.md": "# Test\n\ntext <b>bold</b> text\n",
            }
        )
        try:
            html = (outdir / "index.html").read_text()
            self.assertIn("<b>bold</b>", html)
        finally:
            app.cleanup()

    def test_code_block(self):
        app, outdir, _ = _build(
            files={
                "index.md": "# Test\n\n```python\nprint('hello')\n```\n",
            }
        )
        try:
            html = (outdir / "index.html").read_text()
            self.assertIn("print", html)
        finally:
            app.cleanup()

    def test_multiple_documents(self):
        """Ensure converter state doesn't leak between documents."""
        app, outdir, _ = _build(
            files={
                "index.md": (
                    "# Index\n\ntext <b>bold</b> text\n\n```{toctree}\ndoc2\n```\n"
                ),
                "doc2.md": "# Doc 2\n\nPlain text only.\n",
            }
        )
        try:
            html1 = (outdir / "index.html").read_text()
            html2 = (outdir / "doc2.html").read_text()
            self.assertIn("<b>bold</b>", html1)
            self.assertIn("Plain text only", html2)
            # raw-html-m2r role should NOT appear in doc2 (no HTML there)
            self.assertNotIn("raw-html-m2r", html2)
        finally:
            app.cleanup()


class TestMdInclude(TestCase):
    """Test the mdinclude directive."""

    def test_basic_include(self):
        app, outdir, _ = _build(
            files={
                "index.rst": "Test\n====\n\n.. mdinclude:: included.md\n",
                "included.md": "## Included Section\n\nIncluded content.\n",
            }
        )
        try:
            html = (outdir / "index.html").read_text()
            self.assertIn("Included Section", html)
            self.assertIn("Included content", html)
        finally:
            app.cleanup()

    def test_start_line_zero(self):
        """Regression: start-line=0 must not be treated as falsy."""
        app, outdir, _ = _build(
            files={
                "index.rst": (
                    "Test\n====\n\n"
                    ".. mdinclude:: included.md\n"
                    "   :start-line: 0\n"
                    "   :end-line: 2\n"
                ),
                "included.md": "line0\n\nline2\n\nline4\n",
            }
        )
        try:
            html = (outdir / "index.html").read_text()
            self.assertIn("line0", html)
            self.assertNotIn("line4", html)
        finally:
            app.cleanup()

    def test_end_line_only(self):
        app, outdir, _ = _build(
            files={
                "index.rst": (
                    "Test\n====\n\n.. mdinclude:: included.md\n   :end-line: 1\n"
                ),
                "included.md": "first\n\nsecond\n",
            }
        )
        try:
            html = (outdir / "index.html").read_text()
            self.assertIn("first", html)
            self.assertNotIn("second", html)
        finally:
            app.cleanup()

    def test_start_line_only(self):
        app, outdir, _ = _build(
            files={
                "index.rst": (
                    "Test\n====\n\n.. mdinclude:: included.md\n   :start-line: 2\n"
                ),
                "included.md": "first\n\nsecond\n",
            }
        )
        try:
            html = (outdir / "index.html").read_text()
            self.assertNotIn("first", html)
            self.assertIn("second", html)
        finally:
            app.cleanup()

    def test_include_with_config_options(self):
        """mdinclude should respect Sphinx m2r2 config."""
        app, outdir, _ = _build(
            conf="no_underscore_emphasis = True",
            files={
                "index.rst": "Test\n====\n\n.. mdinclude:: included.md\n",
                "included.md": "_underscored_\n",
            },
        )
        try:
            html = (outdir / "index.html").read_text()
            self.assertIn("_underscored_", html)
        finally:
            app.cleanup()
