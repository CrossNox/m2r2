"""Sphinx integration tests for m2r2."""

import warnings
from pathlib import Path

from docutils import nodes
from sphinx.errors import ConfigError, ExtensionError
from sphinx.testing.util import SphinxTestApp

from m2r2 import __version__
from tests.sphinx_project import SphinxProjectTestBase


class TestGithubAlerts(SphinxProjectTestBase):
    def test_render_alerts_in_markdown_pages_and_includes(self):
        app, outdir, warning = self.build_html_project_with_m2r2(
            {
                "index.md": (
                    "# Alerts\n\n> [!WARNING]\n> Back up your **files**.\n\n"
                    ".. mdinclude:: part.txt\n"
                ),
                "part.txt": "> [!TIP]\n> Read the `guide`.\n",
            }
        )
        self.assertEqual(warning, "")
        document = app.env.get_doctree("index")
        self.assertEqual(
            [node.tagname for node in document.findall(nodes.Admonition)],
            ["warning", "tip"],
        )
        body = (outdir / "index.html").read_text()
        self.assertIn('class="admonition warning"', body)
        self.assertIn('class="admonition tip"', body)
        self.assertNotIn("[!WARNING]", body)
        self.assertNotIn("[!TIP]", body)


class TestInlineMathConfig(SphinxProjectTestBase):
    def build_math_project(self, configuration):
        return self.build_html_project_with_m2r2(
            {
                "index.md": "# Math\n\n`$old$` $new$ $`quoted`$\n\n.. mdinclude:: part.txt\n",
                "part.txt": "$included$\n",
            },
            extra_conf_py=configuration,
        )

    def test_dollar_math_in_pages_and_includes(self):
        app, _, warning = self.build_math_project('m2r_inline_math = "dollar"')
        self.assertEqual(warning, "")
        self.assertEqual(
            [
                node.astext()
                for node in app.env.get_doctree("index").findall(nodes.math)
            ],
            ["new", "quoted", "included"],
        )

    def test_disable_inline_math(self):
        app, _, warning = self.build_math_project("m2r_inline_math = None")
        self.assertEqual(warning, "")
        self.assertEqual(list(app.env.get_doctree("index").findall(nodes.math)), [])

    def test_deprecated_disable_alias(self):
        app, _, warning = self.build_math_project("m2r_disable_inline_math = True")
        self.assertIsNone(app.config.m2r_inline_math)
        self.assertIn("m2r_disable_inline_math", warning)
        self.assertIn("deprecated", warning)
        self.assertEqual(list(app.env.get_doctree("index").findall(nodes.math)), [])

    def test_deprecated_false_alias_preserves_legacy_math(self):
        app, _, warning = self.build_math_project("m2r_disable_inline_math = False")
        self.assertEqual(app.config.m2r_inline_math, "legacy")
        self.assertIn("deprecated", warning)
        self.assertEqual(
            [
                node.astext()
                for node in app.env.get_doctree("index").findall(nodes.math)
            ],
            ["old"],
        )

    def test_new_option_takes_precedence_over_deprecated_alias(self):
        app, _, warning = self.build_math_project(
            'm2r_disable_inline_math = True\nm2r_inline_math = "dollar"'
        )
        self.assertEqual(app.config.m2r_inline_math, "dollar")
        self.assertIn("deprecated", warning)
        self.assertEqual(
            [
                node.astext()
                for node in app.env.get_doctree("index").findall(nodes.math)
            ],
            ["new", "quoted", "included"],
        )

    def test_invalid_mode_raises_configuration_error(self):
        with self.assertRaisesRegex(ConfigError, "m2r_inline_math"):
            self.build_math_project('m2r_inline_math = "unknown"')

    def test_string_false_alias_from_older_sphinx_keeps_math(self):
        app, _, warning = self.build_math_project('m2r_disable_inline_math = "0"')
        self.assertEqual(app.config.m2r_inline_math, "legacy")
        self.assertIn("deprecated", warning)
        self.assertNotIn("has type", warning)
        self.assertEqual(
            [
                node.astext()
                for node in app.env.get_doctree("index").findall(nodes.math)
            ],
            ["old"],
        )

    def test_string_true_alias_from_older_sphinx_disables_math(self):
        app, _, warning = self.build_math_project('m2r_disable_inline_math = "1"')
        self.assertIsNone(app.config.m2r_inline_math)
        self.assertIn("deprecated", warning)
        self.assertNotIn("has type", warning)
        self.assertEqual(list(app.env.get_doctree("index").findall(nodes.math)), [])

    def test_none_takes_precedence_over_deprecated_false_alias(self):
        app, _, warning = self.build_math_project(
            "m2r_disable_inline_math = False\nm2r_inline_math = None"
        )
        self.assertIsNone(app.config.m2r_inline_math)
        self.assertIn("deprecated", warning)
        self.assertEqual(list(app.env.get_doctree("index").findall(nodes.math)), [])

    def test_invalid_alias_raises_configuration_error(self):
        with self.assertRaisesRegex(ConfigError, "m2r_disable_inline_math"):
            self.build_math_project('m2r_disable_inline_math = "unknown"')


class TestSetup(SphinxProjectTestBase):
    """Test the Sphinx extension setup() function."""

    def test_config_defaults_registered(self):
        app, _, _ = self.build_html_project_with_m2r2(
            source_files_by_name={"index.md": "# Hello\n"}
        )
        self.assertFalse(app.config.m2r_no_underscore_emphasis)
        self.assertFalse(app.config.m2r_parse_relative_links)
        self.assertFalse(app.config.m2r_anonymous_references)
        self.assertEqual(app.config.m2r_inline_math, "legacy")
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


class TestM2R2Parser(SphinxProjectTestBase):
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


class TestAlongsideOtherMarkdownParser(SphinxProjectTestBase):
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


class TestIncludedImages(SphinxProjectTestBase):
    def test_strikethrough_image_in_include_is_copied(self):
        app, outdir, warning = self.build_html_project_with_m2r2(
            {
                "index.rst": "Index\n=====\n\n.. mdinclude:: parts/part.txt\n",
                "parts/part.txt": "~~![Logo](logo.svg)~~\n",
                "parts/logo.svg": "<svg/>",
            }
        )

        self.assertEqual(warning, "")
        images = list(app.env.get_doctree("index").findall(nodes.image))
        self.assertGreater(len(images), 0)
        self.assertTrue(all(image["alt"] == "Logo" for image in images))
        self.assertTrue((outdir / "_images" / "logo.svg").exists())
        self.assertRegex(
            (outdir / "index.html").read_text(),
            r'<del>.*<img[^>]+src="_images/logo\.svg"[^>]*>.*</del>',
        )

    svg = '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>'

    def test_resolve_readme_images_outside_source_directory(self):
        app, outdir, warning = self.build_html_project_with_m2r2(
            {
                "index.rst": "Images\n======\n\n.. mdinclude:: ../README.md\n",
                "../README.md": (
                    "![Block](assets/block.svg)\n\n"
                    "Inline ![Inline](assets/inline.svg) image.\n\n"
                    "[![Linked](assets/linked.svg)](https://example.org)\n\n"
                    "| Image |\n| --- |\n| ![Table](assets/table.svg) |\n\n"
                    "![Reference][badge]\n\n[badge]: assets/reference.svg\n\n"
                    "Footnote[^image].\n\n[^image]: See ![Footnote](assets/footnote.svg).\n"
                ),
                **{
                    f"../assets/{name}.svg": self.svg
                    for name in (
                        "block",
                        "inline",
                        "linked",
                        "table",
                        "reference",
                        "footnote",
                    )
                },
            }
        )
        self.assertEqual(warning, "")
        images = list(app.env.get_doctree("index").findall(nodes.image))
        self.assertEqual(
            {image["uri"] for image in images},
            {
                f"../assets/{name}.svg"
                for name in (
                    "block",
                    "inline",
                    "linked",
                    "table",
                    "reference",
                    "footnote",
                )
            },
        )
        dependencies = {
            (Path(app.srcdir) / path).resolve()
            for path in app.env.dependencies["index"]
        }
        for image in images:
            filename = Path(image["uri"]).name
            self.assertEqual((outdir / "_images" / filename).read_text(), self.svg)
            self.assertIn((Path(app.srcdir) / image["uri"]).resolve(), dependencies)
        body = (outdir / "index.html").read_text()
        self.assertIn('href="https://example.org"', body)

    def test_resolve_nested_includes_from_each_markdown_directory(self):
        app, outdir, warning = self.build_html_project_with_m2r2(
            {
                "index.rst": "Images\n======\n\n.. toctree::\n\n   sub/page\n",
                "sub/page.rst": "Page\n====\n\n.. mdinclude:: ../../README.md\n",
                "../README.md": (
                    "![Outer](assets/outer.svg)\n\n.. mdinclude:: parts/inner.txt\n"
                ),
                "../assets/outer.svg": self.svg,
                "../parts/inner.txt": "![Inner](assets/inner.svg)\n",
                "../parts/assets/inner.svg": self.svg,
            }
        )
        self.assertEqual(warning, "")
        images = list(app.env.get_doctree("sub/page").findall(nodes.image))
        self.assertEqual(
            [image["uri"] for image in images],
            ["../assets/outer.svg", "../parts/assets/inner.svg"],
        )
        body = (outdir / "sub" / "page.html").read_text()
        for filename in ("outer.svg", "inner.svg"):
            self.assertTrue((outdir / "_images" / filename).is_file())
            self.assertIn(f'src="../_images/{filename}"', body)

    def test_distinguish_identical_image_names_in_different_includes(self):
        app, outdir, warning = self.build_html_project_with_m2r2(
            {
                "index.md": (
                    "# Images\n\nBefore ![Badge](badge.svg) after.\n\n"
                    ".. mdinclude:: first/part.txt\n\n"
                    ".. mdinclude:: second/part.txt\n\n"
                    ".. mdinclude:: first/part.txt\n"
                ),
                "badge.svg": self.svg,
                "first/part.txt": "Before ![Badge](badge.svg) after.\n",
                "first/badge.svg": self.svg.replace('width="10"', 'width="20"'),
                "second/part.txt": "Before ![Badge](badge.svg) after.\n",
                "second/badge.svg": self.svg.replace('width="10"', 'width="30"'),
            }
        )
        self.assertEqual(warning, "")
        images = [
            image
            for paragraph in app.env.get_doctree("index").findall(nodes.paragraph)
            for image in paragraph.findall(nodes.image)
        ]
        self.assertEqual(
            [image["uri"] for image in images],
            ["badge.svg", "first/badge.svg", "second/badge.svg", "first/badge.svg"],
        )
        for uri in ("badge.svg", "first/badge.svg", "second/badge.svg"):
            filename = app.env.images[uri][1]
            self.assertEqual(
                (outdir / "_images" / filename).read_text(),
                (Path(app.srcdir) / uri).read_text(),
            )

    def test_keep_remote_and_source_root_image_paths(self):
        app, _, warning = self.build_html_project_with_m2r2(
            {
                "index.rst": "Images\n======\n\n.. mdinclude:: parts/images.txt\n",
                "parts/images.txt": (
                    "![Remote](https://example.org/badge.svg)\n\n"
                    "![Root](/assets/root.svg)\n"
                ),
                "assets/root.svg": self.svg,
            }
        )
        self.assertEqual(warning, "")
        self.assertEqual(
            [
                image["uri"]
                for image in app.env.get_doctree("index").findall(nodes.image)
            ],
            ["https://example.org/badge.svg", "assets/root.svg"],
        )

    def test_report_missing_image_relative_to_included_file(self):
        _, _, warning = self.build_html_project_with_m2r2(
            {
                "index.rst": "Images\n======\n\n.. mdinclude:: parts/images.txt\n",
                "parts/images.txt": "![Missing](missing.svg)\n",
            }
        )
        self.assertIn("image file not readable: parts/missing.svg", warning)


class TestMdInclude(SphinxProjectTestBase):
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

    def build_include_of_selected_lines(self, options):
        """Include a five-line Markdown file, one word a line, with the given options."""
        _, outdir, warning = self.build_html_project_with_m2r2(
            source_files_by_name={
                "index.rst": "Test\n====\n\n.. mdinclude:: numbers.txt\n"
                + "".join(f"   :{name}: {value}\n" for name, value in options.items()),
                "numbers.txt": "one\ntwo\nthree\nfour\nfive\n",
            }
        )
        html = (outdir / "index.html").read_text()
        body = html.split("</h1>", 1)[1].split("</section>", 1)[0]
        return body, warning

    def assert_selected_words(self, body, selected):
        for word in ("one", "two", "three", "four", "five"):
            with self.subTest(word=word):
                if word in selected:
                    self.assertIn(word, body)
                else:
                    self.assertNotIn(word, body)

    def test_lines_single_number(self):
        body, warning = self.build_include_of_selected_lines({"lines": "2"})
        self.assertEqual(warning, "")
        self.assert_selected_words(body, {"two"})

    def test_lines_range(self):
        body, warning = self.build_include_of_selected_lines({"lines": "2-3"})
        self.assertEqual(warning, "")
        self.assert_selected_words(body, {"two", "three"})

    def test_lines_open_ranges(self):
        body, warning = self.build_include_of_selected_lines({"lines": "-2, 5-"})
        self.assertEqual(warning, "")
        self.assert_selected_words(body, {"one", "two", "five"})

    def test_lines_come_out_in_the_order_named(self):
        body, warning = self.build_include_of_selected_lines({"lines": "4, 1"})
        self.assertEqual(warning, "")
        self.assert_selected_words(body, {"four", "one"})
        self.assertLess(body.index("four"), body.index("one"))

    def test_lines_then_markers(self):
        body, warning = self.build_include_of_selected_lines(
            {"lines": "2-5", "start-after": "three", "end-before": "five"}
        )
        self.assertEqual(warning, "")
        self.assert_selected_words(body, {"four"})

    def test_lines_with_start_line_is_an_error(self):
        _, warning = self.build_include_of_selected_lines(
            {"lines": "2", "start-line": "1"}
        )
        self.assertIn(
            'Problem with "lines" option of "mdinclude" directive:\n'
            'It cannot be combined with "start-line" or "end-line".',
            warning,
        )

    def test_lines_past_the_end_is_an_error(self):
        _, warning = self.build_include_of_selected_lines({"lines": "4-9"})
        self.assertIn("'4-9' is outside the file, which has 5 lines.", warning)

    def test_lines_backwards_range_is_an_error(self):
        _, warning = self.build_include_of_selected_lines({"lines": "4-2"})
        self.assertIn("The range '4-2' ends before it starts.", warning)

    def test_lines_unreadable_entry_is_an_error(self):
        _, warning = self.build_include_of_selected_lines({"lines": "1, x"})
        self.assertIn("Cannot read 'x' as a line or a range of lines.", warning)

    def test_lines_with_literal_is_an_error(self):
        _, warning = self.build_include_of_selected_lines({"lines": "2", "literal": ""})
        self.assertIn(
            'It cannot be combined with "literal" or "code".',
            warning,
        )

    def build_include_shown_as_source(self, options):
        """Include a Markdown file with options that show it instead of converting."""
        return self.build_html_project_with_m2r2(
            source_files_by_name={
                "index.rst": "Test\n====\n\n.. mdinclude:: part.txt\n"
                + "".join(f"   :{name}: {value}\n" for name, value in options.items()),
                "part.txt": "Some **bold** text.\n",
            }
        )

    def find_only_literal_block(self, app):
        blocks = list(app.env.get_doctree("index").findall(nodes.literal_block))
        self.assertEqual(len(blocks), 1)
        return blocks[0]

    def test_literal_shows_the_markdown_source(self):
        app, _, warning = self.build_include_shown_as_source({"literal": ""})
        self.assertEqual(warning, "")
        self.assertIn("Some **bold** text.", self.find_only_literal_block(app).astext())
        strong = list(app.env.get_doctree("index").findall(nodes.strong))
        self.assertEqual(len(strong), 0)

    def test_code_shows_the_markdown_source(self):
        app, _, warning = self.build_include_shown_as_source({"code": "markdown"})
        self.assertEqual(warning, "")
        block = self.find_only_literal_block(app)
        self.assertIn("Some **bold** text.", block.astext())
        self.assertIn("markdown", block["classes"])

    def test_number_lines(self):
        _, outdir, warning = self.build_include_shown_as_source(
            {"code": "markdown", "number-lines": ""}
        )
        self.assertEqual(warning, "")
        self.assertIn(
            '<small class="ln">1 </small>', (outdir / "index.html").read_text()
        )

    def test_name_and_class(self):
        app, _, warning = self.build_include_shown_as_source(
            {"literal": "", "name": "source-block", "class": "shown"}
        )
        self.assertEqual(warning, "")
        block = self.find_only_literal_block(app)
        self.assertIn("source-block", block["ids"])
        self.assertIn("shown", block["classes"])

    def test_parser_is_rejected(self):
        _, _, warning = self.build_include_shown_as_source({"parser": "rst"})
        self.assertIn(
            'Error in "mdinclude" directive:\nunknown option: "parser".', warning
        )

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
