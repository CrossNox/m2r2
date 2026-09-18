"""Sphinx extension that claims `.md` files the way myst-parser and recommonmark do."""

from docutils import nodes
from docutils.parsers import Parser


class VerbatimMarkdownParser(Parser):
    """Parse Markdown into a titled section holding the raw input."""

    supported = ("markdown", "md")

    def parse(self, inputstring, document):
        """Append `inputstring` to `document` as one paragraph, unparsed."""
        self.setup_parse(inputstring, document)

        # Sphinx warns when a toctree links to a document without a title
        section = nodes.section(ids=["verbatim"], names=["verbatim"])
        section += nodes.title(text="Verbatim")
        section += nodes.paragraph(text=inputstring)
        document += section

        self.finish_parse()


def setup(app):
    """Register `.md` as Markdown and parse it with `VerbatimMarkdownParser`."""
    app.add_source_suffix(".md", "markdown")
    app.add_source_parser(VerbatimMarkdownParser)
    return {"parallel_read_safe": True, "parallel_write_safe": True}
