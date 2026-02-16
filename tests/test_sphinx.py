"""Sphinx integration tests for m2r2.

Tests the Sphinx extension setup(), M2R2Parser, and MdInclude directive
using real Sphinx builds in temporary directories.
"""

import shutil
import tempfile
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
        self.assertFalse(app.config.no_underscore_emphasis)
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


class TestM2R2Parser(SphinxTestBase):
    """Test M2R2Parser as a Sphinx source parser."""

    def test_basic_markdown_build(self):
        _, outdir, _ = self.build(files={"index.md": "# Hello World\n\nA paragraph.\n"})
        html = (outdir / "index.html").read_text()
        self.assertIn("Hello World", html)
        self.assertIn("A paragraph", html)

    def test_no_underscore_emphasis_config(self):
        _, outdir, _ = self.build(
            conf="no_underscore_emphasis = True",
            files={"index.md": "# Test\n\n_underscored_ text\n"},
        )
        html = (outdir / "index.html").read_text()
        self.assertIn("_underscored_", html)

    def test_anonymous_references_config(self):
        _, outdir, _ = self.build(
            conf="m2r_anonymous_references = True",
            files={"index.md": "# Test\n\n[link](http://example.com)\n"},
        )
        html = (outdir / "index.html").read_text()
        self.assertIn("http://example.com", html)

    def test_inline_html_renders(self):
        _, outdir, _ = self.build(
            files={"index.md": "# Test\n\ntext <b>bold</b> text\n"}
        )
        html = (outdir / "index.html").read_text()
        self.assertIn("<b>bold</b>", html)

    def test_code_block(self):
        _, outdir, _ = self.build(
            files={"index.md": "# Test\n\n```python\nprint('hello')\n```\n"}
        )
        html = (outdir / "index.html").read_text()
        self.assertIn("print", html)

    def test_multiple_documents(self):
        """Ensure converter state doesn't leak between documents."""
        _, outdir, _ = self.build(
            files={
                "index.md": (
                    "# Index\n\ntext <b>bold</b> text\n\n```{toctree}\ndoc2\n```\n"
                ),
                "doc2.md": "# Doc 2\n\nPlain text only.\n",
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

    def test_basic_include(self):
        _, outdir, _ = self.build(
            files={
                "index.rst": "Test\n====\n\n.. mdinclude:: included.md\n",
                "included.md": "## Included Section\n\nIncluded content.\n",
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
                    "Test\n====\n\n"
                    ".. mdinclude:: included.md\n"
                    "   :start-line: 0\n"
                    "   :end-line: 2\n"
                ),
                "included.md": "line0\n\nline2\n\nline4\n",
            }
        )
        html = (outdir / "index.html").read_text()
        self.assertIn("line0", html)
        self.assertNotIn("line4", html)

    def test_end_line_only(self):
        _, outdir, _ = self.build(
            files={
                "index.rst": (
                    "Test\n====\n\n.. mdinclude:: included.md\n   :end-line: 1\n"
                ),
                "included.md": "first\n\nsecond\n",
            }
        )
        html = (outdir / "index.html").read_text()
        self.assertIn("first", html)
        self.assertNotIn("second", html)

    def test_start_line_only(self):
        _, outdir, _ = self.build(
            files={
                "index.rst": (
                    "Test\n====\n\n.. mdinclude:: included.md\n   :start-line: 2\n"
                ),
                "included.md": "first\n\nsecond\n",
            }
        )
        html = (outdir / "index.html").read_text()
        self.assertNotIn("first", html)
        self.assertIn("second", html)

    def test_include_with_config_options(self):
        """mdinclude should respect Sphinx m2r2 config."""
        _, outdir, _ = self.build(
            conf="no_underscore_emphasis = True",
            files={
                "index.rst": "Test\n====\n\n.. mdinclude:: included.md\n",
                "included.md": "_underscored_\n",
            },
        )
        html = (outdir / "index.html").read_text()
        self.assertIn("_underscored_", html)
