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
    find_heading_anchors,
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


class TestHeadingAnchorMap(AnchorProjectTestBase):
    """Each document records which section every GitHub anchor names."""

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
        self.assertEqual(
            find_heading_anchors(app.env)["index"],
            {
                "title": section_ids[0],
                "bugfixes": section_ids[1],
                "bugfixes-1": section_ids[2],
                "version-10": section_ids[3],
            },
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

        anchors = find_heading_anchors(app.env)
        for number in range(6):
            with self.subTest(page=number):
                self.assertEqual(
                    set(anchors[f"page{number}"]), {f"page-{number}", "part"}
                )

    def test_rebuild_forgets_a_removed_heading(self):
        srcdir = self.create_project({"index.md": "# Title\n\n## Gone\n\ntext\n"})
        self.build_project(srcdir)

        (srcdir / "index.md").write_text("# Title\n\ntext\n")
        app, _ = self.build_project(srcdir, freshenv=False)

        self.assertEqual(set(find_heading_anchors(app.env)["index"]), {"title"})
