"""Check image URI resolution for Markdown included in Sphinx documents."""

import pytest
from docutils.utils import new_document

from m2r2.sphinx.converter import SphinxRestRenderer


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("assets/badge.svg", "../../assets/badge.svg"),
        ("./assets/badge.svg", "../../assets/badge.svg"),
        ("assets/badge.svg?version=1#icon", "../../assets/badge.svg?version=1#icon"),
        ("assets/my%20badge.svg", "../../assets/my%20badge.svg"),
        ("/assets/badge.svg", "/assets/badge.svg"),
        ("https://example.org/badge.svg", "https://example.org/badge.svg"),
        ("//example.org/badge.svg", "//example.org/badge.svg"),
        ("data:image/png;base64,AAAA", "data:image/png;base64,AAAA"),
        ("", ""),
        ("#icon", "#icon"),
    ],
)
def test_resolve_only_relative_image_file_paths(tmp_path, source, expected):
    renderer = SphinxRestRenderer(
        new_document(str(tmp_path / "docs" / "sub" / "page.rst")),
        str(tmp_path / "README.md"),
        parse_relative_links=False,
        anonymous_references=False,
        use_mermaid=False,
    )
    assert renderer.resolve_image_path(source) == expected
