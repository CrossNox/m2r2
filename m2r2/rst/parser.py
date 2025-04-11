import re
from typing import Match

import mistune
from m2r2.typing import Element, State, Token

# TODO: fix global
_is_sphinx = False


class RestBlockParser(mistune.BlockParser):
    DIRECTIVE = re.compile(
        r"^( *\.\..*?)\n(?=\S)",
        re.DOTALL | re.MULTILINE,
    )
    ONELINE_DIRECTIVE = re.compile(
        r"^( *\.\..*?)$",
        re.DOTALL | re.MULTILINE,
    )
    REST_CODE_BLOCK = re.compile(
        r"^::\s*$",
        re.DOTALL | re.MULTILINE,
    )

    DEFAULT_RULES = (
        "directive",
        "oneline_directive",
        "rest_code_block",
    ) + mistune.BlockParser.DEFAULT_RULES

    def parse_directive(self, match: Match, state: State) -> Token:
        return {"type": "directive", "text": match.group(1)}

    def parse_oneline_directive(self, match: Match, state: State) -> Token:
        # reuse directive output
        return {"type": "directive", "text": match.group(1)}

    def parse_rest_code_block(self, match: Match, state: State) -> Token:
        return {"type": "rest_code_block", "text": ""}


class RestInlineParser(mistune.InlineParser):
    IMAGE_LINK = re.compile(
        r"\[!\[(?P<alt>.*?)\]\((?P<url>.*?)\).*?\]\((?P<target>.*?)\)"
    )
    REST_ROLE = re.compile(r":.*?:`.*?`|`[^`]+`:.*?:")
    REST_LINK = re.compile(r"`[^`]*?`_")
    INLINE_MATH = re.compile(r"`\$(.*?)\$`")
    EOL_LITERAL_MARKER = re.compile(r"(\s+)?::\s*$")
    # add colon and space as special text
    TEXT = re.compile(r"^[\s\S]+?(?=[\\<!\[:_*`~ ]|https?://| {2,}\n|$)")
    # __word__ or **word**
    DOUBLE_EMPHASIS = re.compile(r"^([_*]){2}(?P<text>[\s\S]+?)\1{2}(?!\1)")
    # _word_ or *word*
    EMPHASIS = re.compile(
        r"^\b_((?:__|[^_])+?)_\b"  # _word_
        r"|"
        r"^\*(?P<text>(?:\*\*|[^\*])+?)\*(?!\*)"  # *word*
    )

    DEFAULT_RULES = (
        "inline_math",
        "image_link",
        "rest_role",
        "rest_link",
        "eol_literal_marker",
    ) + mistune.InlineParser.DEFAULT_RULES

    def parse_double_emphasis(self, match: Match, state: State) -> Element:
        # may include code span
        return "double_emphasis", match.group("text")

    def parse_emphasis(self, m: Match, state: State) -> Element:
        # may include code span
        return "emphasis", m.group("text") or m.group(1)

    def parse_image_link(self, match: Match, state: State) -> Element:
        """Pass through rest role."""
        alt, src, target = match.groups()
        return "image_link", src, target, alt

    def parse_rest_role(self, match: Match, state: State) -> Element:
        """Pass through rest role."""
        return "rest_role", match.group(0)

    def parse_rest_link(self, match: Match, state: State) -> Element:
        """Pass through rest link."""
        return "rest_link", match.group(0)

    def parse_inline_math(self, match: Match, state: State) -> Element:
        """Pass through rest link."""
        return "inline_math", match.group(2)

    def parse_eol_literal_marker(self, match: Match, state: State) -> Element:
        """Pass through rest link."""
        marker = ":" if match.group(1) is None else ""
        return "eol_literal_marker", marker

    def no_underscore_emphasis(self):
        self.DOUBLE_EMPHASIS = re.compile(
            r"^\*{2}(?P<text>[\s\S]+?)\*{2}(?!\*)"  # **word**
        )
        self.EMPHASIS = re.compile(r"^\*(?P<text>(?:\*\*|[^\*])+?)\*(?!\*)")  # *word*

    def __init__(self, renderer, *args, **kwargs):
        no_underscore_emphasis = kwargs.pop("no_underscore_emphasis", False)
        disable_inline_math = kwargs.pop("disable_inline_math", False)
        super().__init__(renderer, *args, **kwargs)
        # if not _is_sphinx:
        #    parse_options()
        # if no_underscore_emphasis or getattr(options, "no_underscore_emphasis", False):
        #    self.rules.no_underscore_emphasis()
        inline_maths = "inline_math" in self.DEFAULT_RULES
        if disable_inline_math:  # or getattr(options, "disable_inline_math", False):
            if inline_maths:
                self.DEFAULT_RULES = tuple(
                    x for x in self.DEFAULT_RULES if x != "inline_math"
                )
        elif not inline_maths:
            self.DEFAULT_RULES = ("inline_math", *self.DEFAULT_RULES)
