"""Sphinx integration tests for m2r2."""

import shutil
import tempfile
import warnings
from io import StringIO
from pathlib import Path
from unittest import TestCase

from docutils import nodes
from sphinx.errors import ExtensionError
from sphinx.testing.util import SphinxTestApp

from m2r2 import __version__


class SphinxTestBase(TestCase):
    """Base class that builds Sphinx projects and cleans them up after each test."""

    def build_html_project_with_m2r2(
        self,
        source_files_by_name: dict[str, str],
        extra_conf_py: str = "",
    ) -> tuple[SphinxTestApp, Path, str]:
        """Build an HTML Sphinx project with m2r2 enabled.

        Return the app, the output directory and the warning log.
        """
        tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmpdir, ignore_errors=True)

        srcdir = Path(tmpdir) / "src"
        srcdir.mkdir()
        (srcdir / "conf.py").write_text(f'extensions = ["m2r2"]\n{extra_conf_py}\n')

        for name, content in source_files_by_name.items():
            (srcdir / name).parent.mkdir(parents=True, exist_ok=True)
            (srcdir / name).write_text(content)

        warning = StringIO()
        app = SphinxTestApp(
            buildername="html",
            srcdir=srcdir,
            freshenv=True,
            status=StringIO(),
            warning=warning,
        )
        self.addCleanup(app.cleanup)

        app.build()
        return app, Path(app.outdir), warning.getvalue()


class TestSetup(SphinxTestBase):
    """Test the Sphinx extension setup() function."""

    def test_config_defaults_registered(self):
        app, _, _ = self.build_html_project_with_m2r2(
            source_files_by_name={"index.md": "# Hello\n"}
        )
        self.assertFalse(app.config.m2r_no_underscore_emphasis)
        self.assertFalse(app.config.m2r_parse_relative_links)
        self.assertFalse(app.config.m2r_anonymous_references)
        self.assertFalse(app.config.m2r_disable_inline_math)
        self.assertFalse(app.config.m2r_use_mermaid)

    def test_md_source_suffix_registered(self):
        app, _, _ = self.build_html_project_with_m2r2(
            source_files_by_name={"index.md": "# Hello\n"}
        )
        self.assertIn(".md", app.config.source_suffix)

    def test_setup_return_value(self):
        """Verify setup() returns proper extension metadata."""
        app, _, _ = self.build_html_project_with_m2r2(
            source_files_by_name={"index.md": "# Hello\n"}
        )
        # Sphinx unpacks the metadata dict into Extension attributes
        ext = app.extensions.get("m2r2")
        self.assertIsNotNone(ext)
        self.assertEqual(ext.version, __version__)
        self.assertTrue(ext.parallel_read_safe)
        self.assertTrue(ext.parallel_write_safe)

    def test_mdinclude_extension_setup_return_value(self):
        app, _, _ = self.build_html_project_with_m2r2(
            extra_conf_py='extensions = ["m2r2.mdinclude"]',
            source_files_by_name={"index.rst": "Hello\n=====\n"},
        )
        ext = app.extensions.get("m2r2.mdinclude")
        self.assertIsNotNone(ext)
        self.assertEqual(ext.version, __version__)
        self.assertTrue(ext.parallel_read_safe)
        self.assertTrue(ext.parallel_write_safe)

    def test_m2r2_listed_with_mdinclude_extension(self):
        """Parse `.md` pages and run mdinclude when both extensions are listed."""
        app, _, warning = self.build_html_project_with_m2r2(
            extra_conf_py='extensions = ["m2r2.mdinclude", "m2r2"]',
            source_files_by_name={
                "index.md": """\
# Test

.. mdinclude:: included.txt
""",
                "included.txt": "Some *included* text\n",
            },
        )
        self.assertEqual(warning, "")

        emphasis = list(app.env.get_doctree("index").findall(nodes.emphasis))
        self.assertEqual(len(emphasis), 1)
        self.assertEqual(emphasis[0].astext(), "included")

    def test_mermaid_auto_detect(self):
        """m2r_use_mermaid defaults to True when sphinxcontrib.mermaid is loaded."""
        app, outdir, warning = self.build_html_project_with_m2r2(
            extra_conf_py='extensions = ["m2r2", "sphinxcontrib.mermaid"]',
            source_files_by_name={
                "index.md": """\
# Test

```mermaid
graph TD
    A --> B
```
"""
            },
        )
        self.assertTrue(app.config.m2r_use_mermaid)
        self.assertEqual(warning, "")
        self.assertIn('class="mermaid"', (outdir / "index.html").read_text())

    def test_deprecated_no_underscore_emphasis(self):
        """Old 'no_underscore_emphasis' config emits deprecation and still works."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _, outdir, _ = self.build_html_project_with_m2r2(
                extra_conf_py="no_underscore_emphasis = True",
                source_files_by_name={
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
            _, outdir, _ = self.build_html_project_with_m2r2(
                extra_conf_py="""\
no_underscore_emphasis = True
m2r_no_underscore_emphasis = False""",
                source_files_by_name={
                    "index.md": """\
# Test

_underscored_ text
"""
                },
            )
        self.assertIn("<em>underscored</em>", (outdir / "index.html").read_text())


class TestM2R2Parser(SphinxTestBase):
    """Test M2R2Parser as a Sphinx source parser."""

    def test_unlabelled_code_block(self):
        app, _, warning = self.build_html_project_with_m2r2(
            source_files_by_name={"index.md": "```\ncode\n```\n"}
        )
        self.assertEqual(warning, "")
        blocks = list(app.env.get_doctree("index").findall(nodes.literal_block))
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].astext(), "code")
        self.assertNotIn("code", blocks[0]["classes"])

    def test_basic_markdown_build(self):
        _, outdir, _ = self.build_html_project_with_m2r2(
            source_files_by_name={
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
        _, outdir, _ = self.build_html_project_with_m2r2(
            extra_conf_py="m2r_no_underscore_emphasis = True",
            source_files_by_name={
                "index.md": """\
# Test

_underscored_ text
"""
            },
        )
        html = (outdir / "index.html").read_text()
        self.assertIn("_underscored_", html)

    def test_anonymous_references_config(self):
        """Anonymous references create no named target nodes."""
        app, _, _ = self.build_html_project_with_m2r2(
            extra_conf_py="m2r_anonymous_references = True",
            source_files_by_name={
                "index.md": """\
# Test

[link](http://example.com)
"""
            },
        )
        doctree = app.env.get_doctree("index")

        references = list(doctree.findall(nodes.reference))
        self.assertEqual(len(references), 1)
        self.assertEqual(references[0]["refuri"], "http://example.com")

        self.assertEqual(list(doctree.findall(nodes.target)), [])

    def test_inline_html_renders(self):
        _, outdir, _ = self.build_html_project_with_m2r2(
            source_files_by_name={
                "index.md": """\
# Test

text <b>bold</b> text
"""
            }
        )
        html = (outdir / "index.html").read_text()
        self.assertIn("<b>bold</b>", html)

    def test_code_block(self):
        app, _, warning = self.build_html_project_with_m2r2(
            source_files_by_name={
                "index.md": """\
# Test

```python
print('hello')
```
"""
            }
        )
        self.assertEqual(warning, "")
        blocks = list(app.env.get_doctree("index").findall(nodes.literal_block))
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["language"], "python")
        self.assertEqual(blocks[0].astext(), "print('hello')")

    def test_multiple_documents(self):
        """Ensure converter state doesn't leak between documents."""
        # Sphinx reads documents in sorted order, so "plain" is read after "index"
        app, _, warning = self.build_html_project_with_m2r2(
            source_files_by_name={
                "index.md": """\
# Index

text[^1] and before ![A](https://example.com/a.png) after

.. toctree::

   plain

[^1]: leaked note
""",
                "plain.md": """\
# Plain

Plain text only.
""",
            }
        )
        self.assertEqual(warning, "")

        index = app.env.get_doctree("index")
        self.assertEqual(len(list(index.findall(nodes.footnote))), 1)
        self.assertEqual(len(list(index.findall(nodes.substitution_definition))), 1)

        plain = app.env.get_doctree("plain")
        self.assertEqual(list(plain.findall(nodes.footnote)), [])
        self.assertEqual(list(plain.findall(nodes.substitution_definition)), [])
        self.assertEqual(list(plain.findall(nodes.image)), [])


class TestAlongsideOtherMarkdownParser(SphinxTestBase):
    """Test mdinclude in projects where another extension parses `.md` files."""

    def build_project_with_extensions_in_order(
        self, extensions: list[str]
    ) -> tuple[SphinxTestApp, str]:
        """Build a project that mdincludes Markdown and has a `.md` page.

        Return the app and the warning log.
        """
        app, _, warning = self.build_html_project_with_m2r2(
            extra_conf_py=f"extensions = {extensions!r}",
            source_files_by_name={
                "index.rst": """\
Test
====

.. mdinclude:: included.txt

.. toctree::

   page
""",
                "included.txt": "Some *included* text\n",
                "page.md": "Some *page* text\n",
            },
        )
        return app, warning

    def assert_mdinclude_converts_and_other_parser_reads_pages(
        self, app: SphinxTestApp, warning: str
    ):
        """Check mdinclude output and that `.md` pages bypass m2r2."""
        self.assertEqual(warning, "")

        index = app.env.get_doctree("index")
        emphasis = list(index.findall(nodes.emphasis))
        self.assertEqual(len(emphasis), 1)
        self.assertEqual(emphasis[0].astext(), "included")

        page = app.env.get_doctree("page")
        paragraphs = list(page.findall(nodes.paragraph))
        self.assertEqual(len(paragraphs), 1)
        self.assertEqual(paragraphs[0].astext(), "Some *page* text\n")

    def test_other_parser_loaded_before_mdinclude_extension(self):
        app, warning = self.build_project_with_extensions_in_order(
            ["tests.markdown_parser_extension", "m2r2.mdinclude"]
        )
        self.assert_mdinclude_converts_and_other_parser_reads_pages(app, warning)

    def test_other_parser_loaded_after_mdinclude_extension(self):
        app, warning = self.build_project_with_extensions_in_order(
            ["m2r2.mdinclude", "tests.markdown_parser_extension"]
        )
        self.assert_mdinclude_converts_and_other_parser_reads_pages(app, warning)

    def test_m2r2_after_other_parser_suggests_mdinclude_extension(self):
        with self.assertRaisesRegex(ExtensionError, "m2r2.mdinclude"):
            self.build_project_with_extensions_in_order(
                ["tests.markdown_parser_extension", "m2r2"]
            )


class TestMdInclude(SphinxTestBase):
    """Test the mdinclude directive."""

    def test_unlabelled_code_block(self):
        app, _, warning = self.build_html_project_with_m2r2(
            source_files_by_name={
                "index.rst": ".. mdinclude:: code.txt\n",
                "code.txt": "```\ncode\n```\n",
            }
        )
        self.assertEqual(warning, "")
        blocks = list(app.env.get_doctree("index").findall(nodes.literal_block))
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].astext(), "code")
        self.assertNotIn("code", blocks[0]["classes"])

    def test_repeated_image_in_included_tables(self):
        """Render repeated image substitutions across included documents."""
        table = """\
| A | B |
|---|---|
| before ![A](https://example.com/a.png) after | B |
"""
        _, outdir, build_warnings = self.build_html_project_with_m2r2(
            source_files_by_name={
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
        _, outdir, build_warnings = self.build_html_project_with_m2r2(
            source_files_by_name={
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
        _, outdir, _ = self.build_html_project_with_m2r2(
            source_files_by_name={
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

    def test_start_and_end_line_select_range(self):
        _, outdir, _ = self.build_html_project_with_m2r2(
            source_files_by_name={
                "index.rst": (
                    """\
Test
====

.. mdinclude:: included.md
   :start-line: 2
   :end-line: 3
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
        self.assertIn("line2", html)
        self.assertNotIn("line0", html)
        self.assertNotIn("line4", html)

    def test_end_line_only(self):
        _, outdir, _ = self.build_html_project_with_m2r2(
            source_files_by_name={
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
        _, outdir, _ = self.build_html_project_with_m2r2(
            source_files_by_name={
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

    def test_absolute_path_starts_at_the_source_directory(self):
        _, outdir, warning = self.build_html_project_with_m2r2(
            source_files_by_name={
                "index.rst": "Test\n====\n\n.. toctree::\n\n   sub/page\n",
                "sub/page.rst": "Page\n====\n\n.. mdinclude:: /shared.txt\n",
                "shared.txt": "Shared content.\n",
            }
        )
        self.assertEqual(warning, "")
        self.assertIn("Shared content.", (outdir / "sub" / "page.html").read_text())

    def test_included_markdown_source_is_not_reported_outside_a_toctree(self):
        _, _, warning = self.build_html_project_with_m2r2(
            source_files_by_name={
                "index.rst": "Test\n====\n\n.. mdinclude:: part.md\n",
                "part.md": "# Part\n\nPart content.\n",
            }
        )
        self.assertEqual(warning, "")

    def build_include_between_markers(self, options):
        """Include a Markdown file with three sections and the given options."""
        return self.build_html_project_with_m2r2(
            source_files_by_name={
                "index.rst": "Test\n====\n\n.. mdinclude:: included.txt\n"
                + "".join(f"   :{name}: {value}\n" for name, value in options.items()),
                "included.txt": """\
before

<!-- docs-start -->

inside

<!-- docs-end -->

after
""",
            }
        )

    def test_start_after_marker(self):
        _, outdir, warning = self.build_include_between_markers(
            {"start-after": "<!-- docs-start -->"}
        )
        self.assertEqual(warning, "")
        html = (outdir / "index.html").read_text()
        self.assertNotIn("before", html)
        self.assertNotIn("docs-start", html)
        self.assertIn("inside", html)
        self.assertIn("after", html)

    def test_end_before_marker(self):
        _, outdir, warning = self.build_include_between_markers(
            {"end-before": "<!-- docs-end -->"}
        )
        self.assertEqual(warning, "")
        html = (outdir / "index.html").read_text()
        self.assertIn("before", html)
        self.assertIn("inside", html)
        self.assertNotIn("docs-end", html)
        self.assertNotIn("after", html)

    def test_both_markers(self):
        _, outdir, warning = self.build_include_between_markers(
            {"start-after": "<!-- docs-start -->", "end-before": "<!-- docs-end -->"}
        )
        self.assertEqual(warning, "")
        html = (outdir / "index.html").read_text()
        self.assertNotIn("before", html)
        self.assertIn("inside", html)
        self.assertNotIn("after", html)

    def test_markers_apply_after_line_numbers(self):
        """Cutting the lines that hold the start marker leaves nothing to find."""
        _, _, warning = self.build_include_between_markers(
            {"start-line": "4", "start-after": "<!-- docs-start -->"}
        )
        self.assertIn(
            'Problem with "start-after" option of "mdinclude" directive:\nText not found.',
            warning,
        )

    def test_missing_marker_is_a_severe_error(self):
        _, _, warning = self.build_include_between_markers(
            {"start-after": "<!-- nowhere -->"}
        )
        self.assertIn(
            'Problem with "start-after" option of "mdinclude" directive:\nText not found.',
            warning,
        )

    def test_include_with_config_options(self):
        """mdinclude should respect Sphinx m2r2 config."""
        _, outdir, _ = self.build_html_project_with_m2r2(
            extra_conf_py="m2r_no_underscore_emphasis = True",
            source_files_by_name={
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
