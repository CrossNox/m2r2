from docutils.parsers import rst

from m2r2 import M2R2


class M2R2Parser(rst.Parser):
    # Explicitly tell supported formats to sphinx
    supported = ("markdown", "md", "mkd")

    def parse(self, inputstring, document):
        """Parse `inputstring` and populate `document`, a document tree."""
        config = document.settings.env.config
        converter = M2R2.from_sphinx_config(config)
        super().parse(converter(inputstring), document)
