#!/usr/bin/env python3


import re

import mistune
from mistune.plugins.footnotes import footnotes
from mistune.plugins.table import table

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
    @classmethod
    def from_sphinx_config(cls, config):
        """Create an M2R2 instance from Sphinx configuration.

        Args:
            config: Sphinx config object with m2r2 settings.

        Returns:
            M2R2 instance configured according to Sphinx settings.
        """
        return cls(
            no_underscore_emphasis=config.no_underscore_emphasis,
            parse_relative_links=config.m2r_parse_relative_links,
            anonymous_references=config.m2r_anonymous_references,
            disable_inline_math=config.m2r_disable_inline_math,
            use_mermaid=config.m2r_use_mermaid,
            is_sphinx=True,
        )

    def __init__(self, renderer=None, block=None, inline=None, plugins=None, **kwargs):
        disable_inline_math = kwargs.pop("disable_inline_math", False)
        no_underscore_emphasis = kwargs.pop("no_underscore_emphasis", False)
        kwargs.pop("use_mermaid", False)  # Consumed by RestRenderer

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
