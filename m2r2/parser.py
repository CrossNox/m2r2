from docutils.parsers import rst

from m2r2.sphinx.converter import SphinxM2R2


class M2R2Parser(rst.Parser):
    # Explicitly tell supported formats to sphinx
    supported = ("markdown", "md", "mkd")

    def parse(self, inputstring, document):
        """Parse `inputstring` and populate `document`, a document tree."""
        super().parse(SphinxM2R2(document).parse(inputstring), document)
