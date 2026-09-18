from docutils import nodes
from docutils.core import publish_doctree

from m2r2 import convert


def test_many_inline_html_spans():
    """Preserve all HTML spans when role merging requires more than ten passes."""
    source = " ".join(["<b>x</b>"] * 1024)
    expected = f"""\
.. role:: raw-html-m2r(raw)
   :format: html


:raw-html-m2r:`{source}`
"""
    output = convert(source)
    assert output == expected
    document = publish_doctree(
        output,
        settings_overrides={"halt_level": 2},
    )
    raw_html = "".join(node.astext() for node in document.findall(nodes.raw))
    assert raw_html.count("<b>x</b>") == 1024
