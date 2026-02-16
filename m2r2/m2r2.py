import re

import mistune
from mistune.plugins.footnotes import footnotes
from mistune.plugins.table import table

from m2r2.rst.plugins import rst_directives
from m2r2.rst.renderer import RestRenderer

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
    @classmethod
    def from_sphinx_config(cls, config):
        """Create an M2R2 instance from Sphinx configuration.

        Args:
            config: Sphinx config object with m2r2 settings.

        Returns:
            M2R2 instance configured according to Sphinx settings.
        """
        from m2r2.sphinx.m2r2 import M2R2_CONFIG

        kwargs = {kwarg: getattr(config, conf) for conf, kwarg, _ in M2R2_CONFIG}
        return cls(**kwargs, is_sphinx=True)

    def __init__(self, renderer=None, plugins=None, **kwargs):
        disable_inline_math = kwargs.pop("disable_inline_math", False)
        no_underscore_emphasis = kwargs.pop("no_underscore_emphasis", False)

        if renderer is None:
            renderer = RestRenderer(**kwargs)

        if plugins is None:
            plugins = []

        # Create custom plugin function that respects options
        def custom_rst_directives(md):
            rst_directives(md)
            if disable_inline_math and "inline_math" in md.inline.rules:
                md.inline.rules.remove("inline_math")
                if hasattr(md.inline, "_rules"):
                    md.inline._rules.pop("inline_math", None)
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

        # Add table and footnote support
        plugins.append(table)
        plugins.append(footnotes)

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
        while _RAW_HTML_MERGE_PATTERN.search(text):
            text = _RAW_HTML_MERGE_PATTERN.sub(r":raw-html-m2r:`\1\2\3`", text)

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


def convert(text, **kwargs):
    """Convert a Markdown string to reStructuredText.

    Args:
        text: Markdown source text.
        **kwargs: Options passed to M2R2 constructor.

    Returns:
        The converted reStructuredText string.
    """
    return M2R2(**kwargs)(text)
