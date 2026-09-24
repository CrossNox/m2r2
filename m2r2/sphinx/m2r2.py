from docutils.parsers import rst

from m2r2.m2r2 import __version__
from m2r2.sphinx.converter import SphinxM2R2


class M2R2Parser(rst.Parser):
    """Parse Markdown using a Sphinx document's configuration and context."""

    supported = ("markdown", "md", "mkd")

    def parse(self, inputstring, document):
        """Populate the Sphinx document from Markdown source."""
        super().parse(SphinxM2R2(document).parse(inputstring), document)


def setup(app):
    """Load the `m2r2.mdinclude` extension and register the `.md` source parser."""
    # m2r2 works without Sphinx installed, and m2r2/__init__.py imports this module
    from sphinx.errors import ExtensionError

    app.setup_extension("m2r2.mdinclude")

    try:
        if hasattr(app, "add_source_suffix"):
            app.add_source_suffix(".md", "markdown")
            app.add_source_parser(M2R2Parser)
        else:
            app.add_source_parser(".md", M2R2Parser)  # Sphinx 1.7
    except ExtensionError as error:
        raise ExtensionError(
            f"{error}. Another extension already parses .md files. To use only "
            "the mdinclude directive, replace 'm2r2' with 'm2r2.mdinclude' in "
            "extensions."
        ) from error

    return {
        "version": __version__,
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
