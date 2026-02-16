import re
from importlib.metadata import version

import mistune
from mistune.plugins.footnotes import footnotes
from mistune.plugins.formatting import strikethrough
from mistune.plugins.table import table

from m2r2.rst.plugins import rst_directives
from m2r2.rst.renderer import RestRenderer

__version__ = version("m2r2")

# Asterisk-only patterns for no_underscore_emphasis mode
_ASTERISK_EMPHASIS = r"^\*([^\*]+?)\*(?!\*)"
_ASTERISK_STRONG = r"^\*\*([^\*]+?)\*\*(?!\*)"


def _parse_emphasis_no_underscore(inline, m, state):
    """Parse emphasis using only asterisks (ignoring underscores)."""
    token = {"type": "emphasis", "raw": m.group(1)}
    state.append_token(token)
    return m.end()


def _parse_strong_no_underscore(inline, m, state):
    """Parse strong emphasis using only asterisks (ignoring underscores)."""
    token = {"type": "strong", "raw": m.group(1)}
    state.append_token(token)
    return m.end()


# RST role definition prepended to output when raw HTML is used
PROLOG = """\
.. role:: raw-html-m2r(raw)
   :format: html

"""

# Pattern to merge adjacent raw-html-m2r roles
# Matches: :raw-html-m2r:`<tag>`\ text\ :raw-html-m2r:`</tag>`
# and combines into: :raw-html-m2r:`<tag>text</tag>`
_RAW_HTML_MERGE_PATTERN = re.compile(
    r":raw-html-m2r:`([^`]+)`\\ ([^\\:]+)\\ :raw-html-m2r:`([^`]+)`"
)


class M2R2:
    def __init__(
        self,
        renderer=None,
        plugins=None,
        *,
        no_underscore_emphasis: bool = False,
        disable_inline_math: bool = False,
        parse_relative_links: bool = False,
        anonymous_references: bool = False,
        use_mermaid: bool = False,
    ):
        if renderer is None:
            renderer = RestRenderer(
                parse_relative_links=parse_relative_links,
                anonymous_references=anonymous_references,
                use_mermaid=use_mermaid,
            )

        if plugins is None:
            plugins = []

        # Create custom plugin function that respects options
        def custom_rst_directives(md):
            rst_directives(md)
            if disable_inline_math and "inline_math" in md.inline.rules:
                md.inline.rules.remove("inline_math")
            if no_underscore_emphasis:
                md.inline.register(
                    "emphasis",
                    _ASTERISK_EMPHASIS,
                    _parse_emphasis_no_underscore,
                    before="codespan",
                )
                md.inline.register(
                    "strong",
                    _ASTERISK_STRONG,
                    _parse_strong_no_underscore,
                    before="codespan",
                )

        # Add RST directive plugin function
        plugins.append(custom_rst_directives)

        # Add table, footnote, and strikethrough support
        plugins.append(table)
        plugins.append(footnotes)
        plugins.append(strikethrough)

        # Create markdown parser with RST directive support
        self.md = mistune.create_markdown(renderer=renderer, plugins=plugins)
        self.renderer = renderer

    def parse(self, s):
        output = self.md(s)
        return self.post_process(output)

    def __call__(self, s):
        return self.parse(s)

    def post_process(self, text):
        # Ensure output starts with exactly one leading newline
        if not text.startswith("\n"):
            text = "\n" + text
        elif text.startswith("\n\n\n"):
            text = text[1:]

        # Merge adjacent raw-html-m2r roles that mistune v3 splits across tokens.
        # e.g. :raw-html-m2r:`<s>`\ text\ :raw-html-m2r:`</s>`
        #   -> :raw-html-m2r:`<s>text</s>`
        for _ in range(10):
            if not _RAW_HTML_MERGE_PATTERN.search(text):
                break
            text = _RAW_HTML_MERGE_PATTERN.sub(r":raw-html-m2r:`\1\2\3`", text)
        else:
            raise RuntimeError("raw-html-m2r merge did not converge")

        # Clean up RST escape sequences ("\ ") inserted by the renderer around
        # inline roles. These backslash-space pairs are needed in RST to separate
        # inline markup from surrounding text, but become redundant at line
        # boundaries, before periods, or between spaces.
        output = (
            text.replace("\\ \n", "\n")
            .replace("\n\\ ", "\n")
            .replace(" \\ ", " ")
            .replace("\\  ", " ")
            .replace("\\ .", ".")
        )

        if ":raw-html-m2r:" in output:
            return PROLOG + output
        return output


def convert(
    text,
    *,
    no_underscore_emphasis: bool = False,
    disable_inline_math: bool = False,
    parse_relative_links: bool = False,
    anonymous_references: bool = False,
    use_mermaid: bool = False,
):
    """Convert a Markdown string to reStructuredText.

    Args:
        text: Markdown source text.
        no_underscore_emphasis: Disable underscore-based emphasis.
        disable_inline_math: Disable inline math parsing.
        parse_relative_links: Convert relative links to RST references.
        anonymous_references: Use anonymous RST references.
        use_mermaid: Render mermaid code blocks as directives.

    Returns:
        The converted reStructuredText string.
    """
    return M2R2(
        no_underscore_emphasis=no_underscore_emphasis,
        disable_inline_math=disable_inline_math,
        parse_relative_links=parse_relative_links,
        anonymous_references=anonymous_references,
        use_mermaid=use_mermaid,
    )(text)
