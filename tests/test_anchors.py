"""Tests for the GitHub-style heading anchors m2r2 resolves under Sphinx."""

import shutil
import tempfile
from io import StringIO
from pathlib import Path
from unittest import TestCase

from docutils import nodes
from sphinx.testing.util import SphinxTestApp

from m2r2.sphinx.anchors import (
    assign_github_heading_slugs,
    get_or_create_document_anchor_map,
    slugify_heading_like_github,
)


class TestHeadingSlugs(TestCase):
    """Headings get the anchors GitHub gives them."""

    def test_slugify_heading_like_github(self):
        for title, expected in (
            ("Bugfixes", "bugfixes"),
            ("Version 1.0", "version-10"),
            ("Hello, World!", "hello-world"),
            ("run()", "run"),
            ("snake_case name", "snake_case-name"),
            ("a  b", "a--b"),
            ("C++ & Rust", "c--rust"),
            ("Über Café", "über-café"),
            ("party 🎉 time", "party--time"),
            ("already-hyphenated", "already-hyphenated"),
        ):
            with self.subTest(title=title):
                self.assertEqual(slugify_heading_like_github(title), expected)

    def test_repeated_titles_are_numbered(self):
        self.assertEqual(
            assign_github_heading_slugs(
                ["Bugfixes", "Features", "Bugfixes", "Bugfixes"]
            ),
            ["bugfixes", "features", "bugfixes-1", "bugfixes-2"],
        )

    def test_numbering_skips_an_anchor_another_heading_owns(self):
        self.assertEqual(
            assign_github_heading_slugs(["Foo", "Foo 1", "Foo"]),
            ["foo", "foo-1", "foo-2"],
        )


class AnchorProjectTestBase(TestCase):
    """Create Sphinx projects that m2r2 builds, and build them."""

    def create_project(self, source_files_by_name, extra_conf_py=""):
        """Write a project with m2r2 enabled and return its source directory."""
        tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmpdir, ignore_errors=True)

        srcdir = Path(tmpdir) / "src"
        srcdir.mkdir()
        (srcdir / "conf.py").write_text(f'extensions = ["m2r2"]\n{extra_conf_py}\n')
        for name, content in source_files_by_name.items():
            (srcdir / name).write_text(content)
        return srcdir

    def build_project(self, srcdir, *, freshenv=True, parallel=0):
        """Build a project to HTML and return the app and the warning log."""
        warning = StringIO()
        app = SphinxTestApp(
            buildername="html",
            srcdir=srcdir,
            freshenv=freshenv,
            parallel=parallel,
            status=StringIO(),
            warning=warning,
        )
        self.addCleanup(app.cleanup)
        app.build()
        return app, warning.getvalue()


class TestDocumentAnchorMap(AnchorProjectTestBase):
    """Each document records its ids and GitHub heading anchors."""

    def test_anchors_name_the_sections_in_order(self):
        srcdir = self.create_project(
            {
                "index.md": (
                    "# Title\n\n## Bugfixes\n\na\n\n## Bugfixes\n\nb\n\n"
                    "## Version 1.0\n\nc\n"
                ),
            }
        )
        app, _ = self.build_project(srcdir)

        section_ids = [
            section["ids"][0]
            for section in app.env.get_doctree("index").findall(nodes.section)
        ]
        expected_anchors = {
            "title": section_ids[0],
            "bugfixes": section_ids[1],
            "bugfixes-1": section_ids[2],
            "version-10": section_ids[3],
        }
        for section_id in section_ids:
            expected_anchors.setdefault(section_id, section_id)

        self.assertEqual(
            get_or_create_document_anchor_map(app.env)["index"],
            expected_anchors,
        )

    def test_parallel_build_merges_every_document(self):
        pages = {
            f"page{number}.md": f"# Page {number}\n\n## Part\n" for number in range(6)
        }
        toctree = "\n".join(f"   page{number}" for number in range(6))
        srcdir = self.create_project(
            {"index.rst": f"Index\n=====\n\n.. toctree::\n\n{toctree}\n", **pages}
        )
        app, _ = self.build_project(srcdir, parallel=2)

        anchors = get_or_create_document_anchor_map(app.env)
        for number in range(6):
            with self.subTest(page=number):
                self.assertEqual(
                    set(anchors[f"page{number}"]), {f"page-{number}", "part"}
                )

    def test_rebuild_forgets_a_removed_heading(self):
        srcdir = self.create_project({"index.md": "# Title\n\n## Gone\n\ntext\n"})
        first_app, _ = self.build_project(srcdir)
        first_app.cleanup()

        (srcdir / "index.md").write_text("# Title\n\ntext\n")
        app, _ = self.build_project(srcdir, freshenv=False)

        self.assertEqual(
            set(get_or_create_document_anchor_map(app.env)["index"]), {"title"}
        )


class TestDocumentAnchorLinks(AnchorProjectTestBase):
    """Links to document anchors land on the right elements."""

    def find_section_ids(self, app, docname):
        """Return the ids Sphinx gave the sections of a document, in order."""
        return [
            section["ids"][0]
            for section in app.env.get_doctree(docname).findall(nodes.section)
        ]

    def read_built_page(self, app, docname):
        return (Path(app.outdir) / f"{docname}.html").read_text()

    def find_reference_to_text(self, app, docname, text):
        """Return the resolved reference with the given link text."""
        doctree = app.env.get_and_resolve_doctree(docname, app.builder)
        references = [
            reference
            for reference in doctree.findall(nodes.reference)
            if reference.astext() == text
        ]
        self.assertEqual(len(references), 1)
        return references[0]

    def test_link_to_a_repeated_heading(self):
        srcdir = self.create_project(
            {
                "index.md": (
                    "# Title\n\n## Bugfixes\n\na\n\n## Bugfixes\n\nb\n\n"
                    "See [the second](#bugfixes-1).\n"
                ),
            }
        )
        app, warning = self.build_project(srcdir)

        self.assertNotIn("m2r2", warning)
        second_bugfixes_id = self.find_section_ids(app, "index")[2]
        self.assertEqual(
            self.find_reference_to_text(app, "index", "the second")["refid"],
            second_bugfixes_id,
        )

    def test_link_to_a_heading_with_punctuation(self):
        srcdir = self.create_project(
            {"index.md": "# Title\n\n## Version 1.0\n\nSee [it](#version-10).\n"}
        )
        app, warning = self.build_project(srcdir)

        self.assertNotIn("m2r2", warning)
        version_id = self.find_section_ids(app, "index")[1]
        self.assertEqual(
            self.find_reference_to_text(app, "index", "it")["refid"], version_id
        )

    def test_link_to_a_heading_on_another_page(self):
        srcdir = self.create_project(
            {
                "index.md": (
                    "# Index\n\nSee [fixes](other.md#bugfixes-1).\n\n"
                    ".. toctree::\n\n   other\n"
                ),
                "other.md": "# Other\n\n## Bugfixes\n\na\n\n## Bugfixes\n\nb\n",
            },
            extra_conf_py="m2r_parse_relative_links = True",
        )
        app, warning = self.build_project(srcdir)

        self.assertNotIn("m2r2", warning)
        second_bugfixes_id = self.find_section_ids(app, "other")[2]
        self.assertEqual(
            self.find_reference_to_text(app, "index", "fixes")["refuri"],
            f"other.html#{second_bugfixes_id}",
        )

    def test_link_to_a_label_on_the_same_page(self):
        srcdir = self.create_project(
            {
                "index.md": (
                    "# Title\n\nSee [details](#details).\n\n"
                    ".. _details:\n\n## More information\n"
                ),
            }
        )
        app, warning = self.build_project(srcdir)

        self.assertNotIn("m2r2", warning)
        self.assertEqual(
            self.find_reference_to_text(app, "index", "details")["refid"], "details"
        )

    def test_link_to_a_label_on_another_page(self):
        srcdir = self.create_project(
            {
                "index.md": (
                    "# Index\n\nSee [details](other.md#details).\n\n"
                    ".. toctree::\n\n   other\n"
                ),
                "other.md": "# Other\n\n.. _details:\n\n## More information\n",
            },
            extra_conf_py="m2r_parse_relative_links = True",
        )
        app, warning = self.build_project(srcdir)

        self.assertNotIn("m2r2", warning)
        self.assertEqual(
            self.find_reference_to_text(app, "index", "details")["refuri"],
            "other.html#details",
        )

    def test_label_wins_over_a_matching_github_heading_anchor(self):
        srcdir = self.create_project(
            {
                "index.md": (
                    "# Title\n\nSee [details](#version-10).\n\n"
                    "## Version 1.0\n\nHeading target.\n\n"
                    ".. _version-10:\n\n## Label target\n"
                ),
            }
        )
        app, warning = self.build_project(srcdir)

        self.assertNotIn("m2r2", warning)
        self.assertEqual(
            self.find_reference_to_text(app, "index", "details")["refid"],
            "version-10",
        )

    def test_automatic_section_id_does_not_override_a_github_anchor(self):
        srcdir = self.create_project(
            {
                "index.md": "# Title\n\n## Foo\n\n## Foo\n\n## Foo 1\n\n[second](#foo-1)\n"
            }
        )
        app, warning = self.build_project(srcdir)

        self.assertNotIn("m2r2", warning)
        second_foo_id = self.find_section_ids(app, "index")[2]
        self.assertEqual(
            self.find_reference_to_text(app, "index", "second")["refid"], second_foo_id
        )

    def test_unicode_heading_anchor_resolves_from_encoded_or_plain_destination(self):
        srcdir = self.create_project(
            {"index.md": "# Title\n\n## Café\n\n[plain](#café) [encoded](#caf%C3%A9)\n"}
        )
        app, warning = self.build_project(srcdir)

        self.assertNotIn("m2r2", warning)
        section_id = self.find_section_ids(app, "index")[1]
        for text in ("plain", "encoded"):
            self.assertEqual(
                self.find_reference_to_text(app, "index", text)["refid"], section_id
            )

    def test_inline_math_link_text_is_kept(self):
        srcdir = self.create_project(
            {"index.md": "# Title\n\n## Part\n\n[`$x$`](#part)\n"}
        )
        app, warning = self.build_project(srcdir)

        self.assertNotIn("m2r2", warning)
        self.assertEqual(
            self.find_reference_to_text(app, "index", "x")["refid"],
            self.find_section_ids(app, "index")[1],
        )

    def test_encoded_document_path_resolves(self):
        srcdir = self.create_project(
            {
                "index.md": "# Index\n\n[there](caf%C3%A9.md#part)\n\n.. toctree::\n\n   café\n",
                "café.md": "# Café\n\n## Part\n",
            },
            extra_conf_py="m2r_parse_relative_links = True",
        )
        app, warning = self.build_project(srcdir)

        self.assertNotIn("m2r2", warning)
        self.assertEqual(
            self.find_reference_to_text(app, "index", "there")["refuri"],
            f"caf%C3%A9.html#{self.find_section_ids(app, 'café')[1]}",
        )

    def test_heading_with_html_or_strikethrough_resolves(self):
        srcdir = self.create_project(
            {
                "index.md": (
                    "# Title\n\n## ~~Old~~ Part\n\n## <em>New</em> Part\n\n"
                    "[old](#old-part) [new](#new-part)\n"
                )
            }
        )
        app, warning = self.build_project(srcdir)

        self.assertNotIn("m2r2", warning)
        section_ids = self.find_section_ids(app, "index")
        self.assertEqual(
            self.find_reference_to_text(app, "index", "old")["refid"], section_ids[1]
        )
        self.assertEqual(
            self.find_reference_to_text(app, "index", "new")["refid"], section_ids[2]
        )

    def test_link_to_another_page_without_relative_links_stays_an_href(self):
        srcdir = self.create_project(
            {
                "index.md": (
                    "# Index\n\nSee [fixes](other.md#bugfixes-1).\n\n"
                    ".. toctree::\n\n   other\n"
                ),
                "other.md": "# Other\n\n## Bugfixes\n\na\n\n## Bugfixes\n\nb\n",
            }
        )
        app, _ = self.build_project(srcdir)

        self.assertIn('href="other.md#bugfixes-1"', self.read_built_page(app, "index"))

    def test_link_to_a_missing_anchor_warns(self):
        srcdir = self.create_project({"index.md": "# Title\n\nSee [it](#nowhere).\n"})
        app, warning = self.build_project(srcdir)

        self.assertIn("m2r2 found no anchor #nowhere in 'index'", warning)
        self.assertIn("<p>See <span>it</span>.</p>", self.read_built_page(app, "index"))

    def test_link_to_a_missing_document_warns(self):
        srcdir = self.create_project(
            {"index.md": "# Title\n\nSee [it](missing.md#part).\n"},
            extra_conf_py="m2r_parse_relative_links = True",
        )
        _, warning = self.build_project(srcdir)

        self.assertIn(
            "m2r2 found no document 'missing' for the link to 'missing.md#part'",
            warning,
        )

    def test_link_in_included_markdown(self):
        srcdir = self.create_project(
            {
                "index.rst": (
                    "Index\n=====\n\nBugfixes\n--------\n\ntext\n\n"
                    ".. mdinclude:: part.txt\n"
                ),
                "part.txt": "See [fixes](#bugfixes).\n",
            },
            extra_conf_py='extensions = ["m2r2.mdinclude"]',
        )
        app, warning = self.build_project(srcdir)

        self.assertNotIn("m2r2", warning)
        bugfixes_id = self.find_section_ids(app, "index")[1]
        self.assertEqual(
            self.find_reference_to_text(app, "index", "fixes")["refid"], bugfixes_id
        )

    def test_rebuild_still_resolves_links_to_an_unchanged_page(self):
        files = {
            "index.md": (
                "# Index\n\nSee [part](other.md#part).\n\n.. toctree::\n\n   other\n"
            ),
            "other.md": "# Other\n\n## Part\n\ntext\n",
        }
        srcdir = self.create_project(
            files, extra_conf_py="m2r_parse_relative_links = True"
        )
        first_app, _ = self.build_project(srcdir)
        first_app.cleanup()

        (srcdir / "index.md").write_text(files["index.md"] + "\nMore text.\n")
        app, warning = self.build_project(srcdir, freshenv=False)

        self.assertNotIn("m2r2", warning)
        part_id = self.find_section_ids(app, "other")[1]
        self.assertIn(
            f'href="other.html#{part_id}"', self.read_built_page(app, "index")
        )

    def test_rebuild_rewrites_links_when_target_section_ids_change(self):
        srcdir = self.create_project(
            {
                "index.md": "# Index\n\n.. toctree::\n\n   source\n   target\n",
                "source.md": "# Source\n\n[second](target.md#part-1)\n",
                "target.md": "# Target\n\n## Part\n\n## Part\n",
            },
            extra_conf_py="m2r_parse_relative_links = True",
        )
        first_app, first_warning = self.build_project(srcdir)
        self.assertNotIn("m2r2", first_warning)
        old_id = self.find_section_ids(first_app, "target")[2]
        first_app.cleanup()

        (srcdir / "target.md").write_text(
            "# Target\n\n## Extra\n\n## Extra\n\n## Part\n\n## Part\n"
        )
        app, warning = self.build_project(srcdir, freshenv=False)

        self.assertNotIn("m2r2", warning)
        new_id = self.find_section_ids(app, "target")[4]
        self.assertNotEqual(old_id, new_id)
        self.assertIn(
            f'href="target.html#{new_id}"', self.read_built_page(app, "source")
        )

    def test_parallel_build_resolves_links(self):
        pages = {
            f"page{number}.md": (
                f"# Page {number}\n\n## Part\n\nSee [the next](page{(number + 1) % 6}.md#part).\n"
            )
            for number in range(6)
        }
        toctree = "\n".join(f"   page{number}" for number in range(6))
        srcdir = self.create_project(
            {"index.rst": f"Index\n=====\n\n.. toctree::\n\n{toctree}\n", **pages},
            extra_conf_py="m2r_parse_relative_links = True",
        )
        app, warning = self.build_project(srcdir, parallel=2)

        self.assertNotIn("m2r2", warning)
        for number in range(6):
            next_number = (number + 1) % 6
            part_id = self.find_section_ids(app, f"page{next_number}")[1]
            with self.subTest(page=number):
                self.assertIn(
                    f'href="page{next_number}.html#{part_id}"',
                    self.read_built_page(app, f"page{number}"),
                )
