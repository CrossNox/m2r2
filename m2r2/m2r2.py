#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals

import mistune
from docutils import statemachine
from docutils.parsers import rst

from m2r2.constants import PROLOG
from m2r2.rst.parser import RestBlockParser, RestInlineParser
from m2r2.rst.renderer import RestRenderer


class M2R2(mistune.Markdown):
    def __init__(self, renderer=None, block=None, inline=None, plugins=None, **kwargs):
        disable_inline_math = kwargs.pop("disable_inline_math", False)
        no_underscore_emphasis = kwargs.pop("no_underscore_emphasis", False)
        renderer = renderer or RestRenderer(**kwargs)
        block = block or RestBlockParser()
        inline = inline or RestInlineParser(
            renderer,
            disable_inline_math=disable_inline_math,
            no_underscore_emphasis=no_underscore_emphasis,
        )
        if plugins is None:
            plugins = []
        super().__init__(renderer=renderer, block=block, inline=inline, plugins=plugins)

    def parse(self, s, state=None):
        output = super().parse(s, state)
        return self.post_process(output)

    def post_process(self, text):
        output = (
            text.replace("\\ \n", "\n")
            .replace("\n\\ ", "\n")
            .replace(" \\ ", " ")
            .replace("\\  ", " ")
            .replace("\\ .", ".")
        )
        if self.renderer._include_raw_html:
            return (
                PROLOG + output
            )  # You might need to define 'prolog' if it's used in your original code
        return output


class M2R2Parser(rst.Parser):
    # Explicitly tell supported formats to sphinx
    supported = ("markdown", "md", "mkd")

    def parse(self, inputstring, document):
        if isinstance(inputstring, statemachine.StringList):
            inputstring = "\n".join(inputstring)
        config = document.settings.env.config
        converter = M2R2(
            no_underscore_emphasis=config.no_underscore_emphasis,
            parse_relative_links=config.m2r_parse_relative_links,
            anonymous_references=config.m2r_anonymous_references,
            disable_inline_math=config.m2r_disable_inline_math,
            use_mermaid=config.m2r_use_mermaid,
        )
        super().parse(converter(inputstring), document)


def convert(text, **kwargs):
    return M2R2(**kwargs)(text)
