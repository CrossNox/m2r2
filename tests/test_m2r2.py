from docutils import nodes
from docutils.core import publish_doctree

from m2r2 import M2R, M2R2


def test_m2r_alias():
    assert M2R is M2R2
    source = """\
# Title

A paragraph."""
    expected = """
Title
=====

A paragraph.
"""
    output = M2R()(source)
    assert output == expected
    document = publish_doctree(
        output,
        settings_overrides={"halt_level": 2},
    )
    assert next(document.findall(nodes.title)).astext() == "Title"
    assert next(document.findall(nodes.paragraph)).astext() == "A paragraph."
