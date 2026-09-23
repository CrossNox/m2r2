"""Build small Sphinx projects for integration tests."""

import shutil
import tempfile
from io import StringIO
from pathlib import Path
from unittest import TestCase

from sphinx.testing.util import SphinxTestApp


class SphinxProjectTestBase(TestCase):
    """Create and build Sphinx projects with m2r2 enabled."""

    def create_project(self, source_files_by_name, extra_conf_py=""):
        """Write source files and return the project's source directory."""
        tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmpdir, ignore_errors=True)

        srcdir = Path(tmpdir) / "src"
        srcdir.mkdir()
        (srcdir / "conf.py").write_text(f'extensions = ["m2r2"]\n{extra_conf_py}\n')
        for name, content in source_files_by_name.items():
            (srcdir / name).parent.mkdir(parents=True, exist_ok=True)
            (srcdir / name).write_text(content)
        return srcdir

    def build_project(self, srcdir, *, freshenv=True, parallel=0):
        """Build HTML and return the app and warning log."""
        warning = StringIO()
        app_options = dict(
            buildername="html",
            srcdir=srcdir,
            freshenv=freshenv,
            status=StringIO(),
            warning=warning,
        )
        if parallel > 0:
            app_options["parallel"] = parallel
        app = SphinxTestApp(**app_options)
        self.addCleanup(app.cleanup)
        app.build()
        return app, warning.getvalue()

    def build_html_project_with_m2r2(self, source_files_by_name, extra_conf_py=""):
        """Create and build a project, returning its app, output path, and warnings."""
        srcdir = self.create_project(source_files_by_name, extra_conf_py)
        app, warning = self.build_project(srcdir)
        return app, Path(app.outdir), warning
