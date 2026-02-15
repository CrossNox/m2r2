#!/usr/bin/env python3


import re

import mistune

from m2r2.constants import PROLOG
from m2r2.rst.plugins import rst_directives
from m2r2.rst.renderer import RestRenderer

# Pattern to merge adjacent raw-html-m2r roles
# Matches: :raw-html-m2r:`<tag>`\ text\ :raw-html-m2r:`</tag>`
# and combines into: :raw-html-m2r:`<tag>text</tag>`
_RAW_HTML_MERGE_PATTERN = re.compile(
    r":raw-html-m2r:`([^`]+)`\\ ([^\\:]+)\\ :raw-html-m2r:`([^`]+)`"
)


class M2R2:
    def __init__(self, renderer=None, block=None, inline=None, plugins=None, **kwargs):
        disable_inline_math = kwargs.pop("disable_inline_math", False)
        no_underscore_emphasis = kwargs.pop("no_underscore_emphasis", False)
        use_mermaid = kwargs.pop("use_mermaid", False)

        # Store the parameters for the renderer
        self.renderer_kwargs = kwargs
        self.disable_inline_math = disable_inline_math
        self.no_underscore_emphasis = no_underscore_emphasis
        self.use_mermaid = use_mermaid

        renderer = renderer or RestRenderer(**kwargs)

        if plugins is None:
            plugins = []

        # Create custom plugin function that respects options
        def custom_rst_directives(md):
            rst_directives(md)
            # Remove inline_math if disabled
            if disable_inline_math and "inline_math" in md.inline.rules:
                md.inline.rules.remove("inline_math")
                if hasattr(md.inline, "_rules"):
                    md.inline._rules.pop("inline_math", None)

            # Handle no_underscore_emphasis option
            if no_underscore_emphasis:
                # Override the built-in emphasis patterns to only use asterisks

                def parse_emphasis_no_underscore(inline, m, state):
                    """Parse emphasis without underscore support"""
                    text = m.group(1)
                    token = {"type": "emphasis", "raw": text}
                    state.append_token(token)
                    return m.end()

                def parse_strong_no_underscore(inline, m, state):
                    """Parse strong emphasis without underscore support"""
                    text = m.group(1)
                    token = {"type": "strong", "raw": text}
                    state.append_token(token)
                    return m.end()

                # Override patterns to only match asterisk-based emphasis
                ASTERISK_EMPHASIS = r"^\*([^\*]+?)\*(?!\*)"
                ASTERISK_STRONG = r"^\*\*([^\*]+?)\*\*(?!\*)"

                # Re-register with asterisk-only patterns
                md.inline.register(
                    "emphasis",
                    ASTERISK_EMPHASIS,
                    parse_emphasis_no_underscore,
                    before="codespan",
                )
                md.inline.register(
                    "strong",
                    ASTERISK_STRONG,
                    parse_strong_no_underscore,
                    before="codespan",
                )

        # Add RST directive plugin function
        plugins.append(custom_rst_directives)

        # Add table and footnote support
        from mistune.plugins.footnotes import footnotes
        from mistune.plugins.table import table

        plugins.append(table)
        plugins.append(footnotes)

        # Create markdown parser with RST directive support
        self.md = mistune.create_markdown(renderer=renderer, plugins=plugins)
        self.renderer = renderer

    def parse(self, s, state=None):
        output = self.md(s)
        return self.post_process(output)

    def __call__(self, s):
        return self.parse(s)

    def post_process(self, text):
        # Add leading newline to match expected output format, but not if already double newline
        if not text.startswith("\n"):
            text = "\n" + text
        elif text.startswith("\n\n\n"):
            # Remove extra leading newline that sometimes gets added
            text = text[1:]

        # Merge adjacent raw-html-m2r roles (mistune v3 tokenizes each HTML tag separately)
        # Keep merging until no more matches (handles nested cases)
        while _RAW_HTML_MERGE_PATTERN.search(text):
            text = _RAW_HTML_MERGE_PATTERN.sub(r":raw-html-m2r:`\1\2\3`", text)

        output = (
            text.replace("\\ \n", "\n")
            .replace("\n\\ ", "\n")
            .replace(" \\ ", " ")
            .replace("\\  ", " ")
            .replace("\\ .", ".")
        )
        if (
            hasattr(self.renderer, "_include_raw_html")
            and self.renderer._include_raw_html
        ):
            return PROLOG + output
        return output


def convert(text, **kwargs):
    return M2R2(**kwargs)(text)
