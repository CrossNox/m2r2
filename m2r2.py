#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M2R2 code"""


from __future__ import print_function, unicode_literals

import os
import os.path
import re
import sys
from argparse import ArgumentParser, Namespace

import mistune
from docutils import io, statemachine, utils
from docutils.parsers import rst
from docutils.utils import column_width

try:
    from pkg_resources import get_distribution
except ImportError:
    from importlib.metadata import distribution as get_distribution

__version__ = get_distribution("m2r2").version

if sys.version_info < (3,):
    from codecs import open as _open

    from urlparse import urlparse
else:
    _open = open
    from urllib.parse import urlparse


_IS_SPHINX = False
PROLOG = """\
.. role:: raw-html-m2r(raw)
   :format: html

"""

# for command-line use
parser = ArgumentParser()
options = Namespace()
parser.add_argument("input_file", nargs="*", help="files to convert to reST format")
parser.add_argument(
    "--overwrite",
    action="store_true",
    default=False,
    help="overwrite output file without confirmaion",
)
parser.add_argument(
    "--dry-run",
    action="store_true",
    default=False,
    help="print conversion result and not save output file",
)
parser.add_argument(
    "--no-underscore-emphasis",
    action="store_true",
    default=False,
    help="do not use underscore (_) for emphasis",
)
parser.add_argument(
    "--parse-relative-links",
    action="store_true",
    default=False,
    help="parse relative links into ref or doc directives",
)
parser.add_argument(
    "--anonymous-references",
    action="store_true",
    default=False,
    help="use anonymous references in generated rst",
)
parser.add_argument(
    "--disable-inline-math",
    action="store_true",
    default=False,
    help="disable parsing inline math",
)


def parse_options():
    """Parse CLI options"""
    parser.parse_known_args(namespace=options)


class RestBlockGrammar(mistune.BlockGrammar):  # pylint: disable=too-few-public-methods
    directive = re.compile(
        r"^( *\.\..*?)\n(?=\S)",
        re.DOTALL | re.MULTILINE,
    )
    oneline_directive = re.compile(
        r"^( *\.\..*?)$",
        re.DOTALL | re.MULTILINE,
    )
    rest_code_block = re.compile(
        r"^::\s*$",
        re.DOTALL | re.MULTILINE,
    )


class RestBlockLexer(mistune.BlockLexer):
    grammar_class = RestBlockGrammar
    default_rules = [
        "directive",
        "oneline_directive",
        "rest_code_block",
    ] + mistune.BlockLexer.default_rules

    def parse_directive(self, m):
        self.tokens.append({"type": "directive", "text": m.group(1)})

    def parse_oneline_directive(self, m):
        # reuse directive output
        self.tokens.append({"type": "directive", "text": m.group(1)})

    def parse_rest_code_block(self, _m):
        self.tokens.append({"type": "rest_code_block"})


class RestInlineGrammar(mistune.InlineGrammar):
    image_link = re.compile(
        r"\[!\[(?P<alt>.*?)\]\((?P<url>.*?)\).*?\]\((?P<target>.*?)\)"
    )
    rest_role = re.compile(r":.*?:`.*?`|`[^`]+`:.*?:")
    rest_link = re.compile(r"`[^`]*?`_")
    inline_math = re.compile(r"`\$(.*?)\$`")
    eol_literal_marker = re.compile(r"(\s+)?::\s*$")
    # add colon and space as special text
    text = re.compile(r"^[\s\S]+?(?=[\\<!\[:_*`~ ]|https?://| {2,}\n|$)")
    # __word__ or **word**
    double_emphasis = re.compile(r"^([_*]){2}(?P<text>[\s\S]+?)\1{2}(?!\1)")
    # _word_ or *word*
    emphasis = re.compile(
        r"^\b_((?:__|[^_])+?)_\b"  # _word_
        r"|"
        r"^\*(?P<text>(?:\*\*|[^\*])+?)\*(?!\*)"  # *word*
    )

    def no_underscore_emphasis(self):
        self.double_emphasis = re.compile(
            r"^\*{2}(?P<text>[\s\S]+?)\*{2}(?!\*)"  # **word**
        )
        self.emphasis = re.compile(r"^\*(?P<text>(?:\*\*|[^\*])+?)\*(?!\*)")  # *word*


class RestInlineLexer(mistune.InlineLexer):
    grammar_class = RestInlineGrammar
    default_rules = [
        "image_link",
        "rest_role",
        "rest_link",
        "eol_literal_marker",
    ] + mistune.InlineLexer.default_rules

    def __init__(self, *args, **kwargs):
        no_underscore_emphasis = kwargs.pop("no_underscore_emphasis", False)
        disable_inline_math = kwargs.pop("disable_inline_math", False)
        super().__init__(*args, **kwargs)
        if not _IS_SPHINX:
            parse_options()
        if no_underscore_emphasis or getattr(options, "no_underscore_emphasis", False):
            self.rules.no_underscore_emphasis()
        inline_maths = "inline_math" in self.default_rules
        if disable_inline_math or getattr(options, "disable_inline_math", False):
            if inline_maths:
                self.default_rules.remove("inline_math")
        elif not inline_maths:
            self.default_rules.insert(0, "inline_math")

    def output_double_emphasis(self, m):
        # may include code span
        text = self.output(m.group("text"))
        return self.renderer.double_emphasis(text)

    def output_emphasis(self, m):
        # may include code span
        text = self.output(m.group("text") or m.group(1))
        return self.renderer.emphasis(text)

    def output_image_link(self, m):
        """Pass through rest role."""
        return self.renderer.image_link(
            m.group("url"), m.group("target"), m.group("alt")
        )

    def output_rest_role(self, m):
        """Pass through rest role."""
        return self.renderer.rest_role(m.group(0))

    def output_rest_link(self, m):
        """Pass through rest link."""
        return self.renderer.rest_link(m.group(0))

    def output_inline_math(self, m):
        """Pass through rest link."""
        return self.renderer.inline_math(m.group(1))

    def output_eol_literal_marker(self, m):
        """Pass through rest link."""
        marker = ":" if m.group(1) is None else ""
        return self.renderer.eol_literal_marker(marker)


class RestRenderer(mistune.Renderer):  # pylint: disable=too-many-public-methods
    _include_raw_html = False
    list_indent_re = re.compile(r"^(\s*(#\.|\*)\s)")
    indent = " " * 3
    list_marker = "{#__rest_list_mark__#}"
    hmarks = {
        1: "=",
        2: "-",
        3: "^",
        4: "~",
        5: '"',
        6: "#",
    }

    def __init__(self, *args, **kwargs):
        self.parse_relative_links = kwargs.pop("parse_relative_links", False)
        self.anonymous_references = kwargs.pop("anonymous_references", False)
        self.use_mermaid = kwargs.pop("use_mermaid", False)
        super().__init__(*args, **kwargs)
        if not _IS_SPHINX:
            parse_options()
            if getattr(options, "parse_relative_links", False):
                self.parse_relative_links = options.parse_relative_links
            if getattr(options, "anonymous_references", False):
                self.anonymous_references = options.anonymous_references

    def _indent_block(self, block):
        return "\n".join(
            self.indent + line if line else "" for line in block.splitlines()
        )

    def _raw_html(self, html):
        self._include_raw_html = True
        return rf"\ :raw-html-m2r:`{html}`\ "

    def block_code(self, code, lang=None):
        if lang == "math":
            first_line = "\n.. math::\n\n"
        elif lang == "mermaid" and self.use_mermaid:
            first_line = "\n.. mermaid::\n\n"
        elif lang:
            first_line = f"\n.. code-block:: {lang}\n\n"
        elif _IS_SPHINX:
            first_line = "\n::\n\n"
        else:
            first_line = "\n.. code-block::\n\n"
        return first_line + self._indent_block(code) + "\n"

    def block_quote(self, text):
        # text includes some empty line
        inner = self._indent_block(text.strip("\n"))
        return f"\n..\n\n{inner}\n\n"

    def block_html(self, html):
        """Rendering block level pure html content.

        :param html: text content of the html snippet.
        """
        return "\n\n.. raw:: html\n\n" + self._indent_block(html) + "\n\n"

    def header(self, text, level, raw=None):
        """Rendering header/heading tags like ``<h1>`` ``<h2>``.

        :param text: rendered text content for the header.
        :param level: a number for the header level, for example: 1.
        :param raw: raw text content of the header.
        """
        return f"\n{text}\n{self.hmarks[level] * column_width(text)}\n"

    def hrule(self):
        """Rendering method for ``<hr>`` tag."""
        return "\n----\n"

    def list(self, body, ordered=True):
        """Rendering list tags like ``<ul>`` and ``<ol>``.

        :param body: body contents of the list.
        :param ordered: whether this list is ordered or not.
        """
        mark = "#. " if ordered else "* "
        lines = body.splitlines()
        for i, line in enumerate(lines):
            if line and not line.startswith(self.list_marker):
                lines[i] = " " * len(mark) + line
        inner = "\n".join(lines)
        return f"\n{inner}\n".replace(self.list_marker, mark)

    def list_item(self, text):
        """Rendering list item snippet. Like ``<li>``."""
        return "\n" + self.list_marker + text

    def paragraph(self, text):
        """Rendering paragraph tags. Like ``<p>``."""
        return "\n" + text + "\n"

    def table(self, header, body):
        """Rendering table element. Wrap header and body in it.

        :param header: header part of the table.
        :param body: body part of the table.
        """
        table = "\n.. list-table::\n"
        if header and not header.isspace():
            table = (
                table
                + self.indent
                + ":header-rows: 1\n\n"
                + self._indent_block(header)
                + "\n"
            )
        else:
            table = table + "\n"
        table = table + self._indent_block(body) + "\n\n"
        return table

    def table_row(self, content):
        """Rendering a table row. Like ``<tr>``.

        :param content: content of current table row.
        """
        contents = content.splitlines()
        if not contents:
            return ""
        clist = ["* " + contents[0]]
        if len(contents) > 1:
            for c in contents[1:]:
                clist.append("  " + c)
        return "\n".join(clist) + "\n"

    def table_cell(self, content, **flags):
        """Rendering a table cell. Like ``<th>`` ``<td>``.

        :param content: content of current table cell.
        :param header: whether this is header or not.
        :param align: align of current table cell.
        """
        return "- " + content + "\n"

    def double_emphasis(self, text):
        """Rendering **strong** text.

        :param text: text content for emphasis.
        """
        return rf"\ **{text}**\ "

    def emphasis(self, text):
        """Rendering *emphasis* text.

        :param text: text content for emphasis.
        """
        return rf"\ *{text}*\ "

    def codespan(self, text):
        """Rendering inline `code` text.

        :param text: text content for inline code.
        """
        if "``" not in text:
            return rf"\ ``{text}``\ "
        # actually, docutils split spaces in literal
        return self._raw_html(
            '<code class="docutils literal">'
            f'<span class="pre">{text.replace("`", "&#96;")}</span>'
            "</code>"
        )

    def linebreak(self):
        """Rendering line break like ``<br>``."""
        if self.options.get("use_xhtml"):
            return self._raw_html("<br />") + "\n"
        return self._raw_html("<br>") + "\n"

    def strikethrough(self, text):
        """Rendering ~~strikethrough~~ text.

        :param text: text content for strikethrough.
        """
        return self._raw_html(f"<del>{text}</del>")

    def text(self, text):
        """Rendering unformatted text.

        :param text: text content.
        """
        return text

    def autolink(self, link, is_email=False):
        """Rendering a given link or email address.

        :param link: link content or email address.
        :param is_email: whether this is an email or not.
        """
        return link

    def link(self, link, title, text):
        """Rendering a given link with content and title.

        :param link: href link for ``<a>`` tag.
        :param title: title content for `title` attribute.
        :param text: text content for description.
        """
        if self.anonymous_references:
            underscore = "__"
        else:
            underscore = "_"
        if title:
            return self._raw_html(f'<a href="{link}" title="{title}">{text}</a>')
        if not self.parse_relative_links:
            return rf"\ `{text} <{link}>`{underscore}\ "
        url_info = urlparse(link)
        if url_info.scheme:
            return rf"\ `{text} <{link}>`{underscore}\ "
        link_type = "doc"
        anchor = url_info.fragment
        if url_info.fragment:
            if url_info.path:
                # Can't link to anchors via doc directive.
                anchor = ""
            else:
                # Example: [text](#anchor)
                link_type = "ref"
        doc_link = f"{os.path.splitext(url_info.path)[0]}{anchor}"
        # splittext approach works whether or not path is set. It
        # will return an empty string if unset, which leads to
        # anchor only ref.
        return rf"\ :{link_type}:`{text} <{doc_link}>`\ "

    def image(self, src, title, text):
        """Rendering a image with title and text.

        :param src: source link of the image.
        :param title: title text of the image.
        :param text: alt text of the image.
        """
        # rst does not support title option
        # and I couldn't find title attribute in HTML standard
        return "\n".join(
            [
                "",
                f".. image:: {src}",
                f"   :target: {src}",
                f"   :alt: {text}",
                "",
            ]
        )

    def inline_html(self, html):
        """Rendering span level pure html content.

        :param html: text content of the html snippet.
        """
        return self._raw_html(html)

    def newline(self):
        """Rendering newline element."""
        return ""

    def footnote_ref(self, key, index):
        """Rendering the ref anchor of a footnote.

        :param key: identity key for the footnote.
        :param index: the index count of current footnote.
        """
        return rf"\ [#fn-{key}]_\ "

    def footnote_item(self, key, text):
        """Rendering a footnote item.

        :param key: identity key for the footnote.
        :param text: text content of the footnote.
        """
        return f".. [#fn-{key}] {text.strip()}\n"

    def footnotes(self, text):
        """Wrapper for all footnotes.

        :param text: contents of all footnotes.
        """
        if text:
            return "\n\n" + text
        return ""

    # Below outputs are for rst

    def image_link(self, url, target, alt):
        return "\n".join(
            [
                "",
                f".. image:: {url}",
                f"   :target: {target}",
                f"   :alt: {alt}",
                "",
            ]
        )

    def rest_role(self, text):
        return text

    def rest_link(self, text):
        return text

    def inline_math(self, math):
        """Extension of recommonmark."""
        return rf":math:`{math}`"

    def eol_literal_marker(self, marker):
        """Extension of recommonmark."""
        return marker

    def directive(self, text):
        return "\n" + text

    def rest_code_block(self):
        return "\n\n"


class M2R(mistune.Markdown):
    def __init__(
        self, renderer=None, inline=RestInlineLexer, block=RestBlockLexer, **kwargs
    ):
        if renderer is None:
            renderer = RestRenderer(**kwargs)
        super().__init__(renderer, inline=inline, block=block, **kwargs)

    def parse(self, text):
        output = super().parse(text)
        return self.post_process(output)

    def output_directive(self):
        return self.renderer.directive(self.token["text"])

    def output_rest_code_block(self):
        return self.renderer.rest_code_block()

    def post_process(self, text):
        output = (
            text.replace("\\ \n", "\n")
            .replace("\n\\ ", "\n")
            .replace(" \\ ", " ")
            .replace("\\  ", " ")
            .replace("\\ .", ".")
        )
        if self.renderer._include_raw_html:  # pylint: disable=protected-access
            return PROLOG + output
        return output


class M2RParser(rst.Parser):
    # Explicitly tell supported formats to sphinx
    supported = ("markdown", "md", "mkd")

    def parse(self, inputstring, document):
        if isinstance(inputstring, statemachine.StringList):
            inputstring_ = "\n".join(inputstring)
        else:
            inputstring_ = inputstring
        config = document.settings.env.config
        converter = M2R(
            no_underscore_emphasis=config.no_underscore_emphasis,
            parse_relative_links=config.m2r_parse_relative_links,
            anonymous_references=config.m2r_anonymous_references,
            disable_inline_math=config.m2r_disable_inline_math,
            use_mermaid=config.m2r_use_mermaid,
        )
        super().parse(converter(inputstring_), document)


class MdInclude(rst.Directive):
    """Directive class to include markdown in sphinx.

    Load a file and convert it to rst and insert as a node. Currently
    directive-specific options are not implemented.
    """

    required_arguments = 1
    optional_arguments = 0
    option_spec = {
        "start-line": int,
        "end-line": int,
    }

    def run(self):
        """Most of this method is from ``docutils.parser.rst.Directive``.

        docutils version: 0.12
        """
        if not self.state.document.settings.file_insertion_enabled:
            raise self.warning(f'"{self.name}" directive disabled.')
        source = self.state_machine.input_lines.source(
            self.lineno - self.state_machine.input_offset - 1
        )
        source_dir = os.path.dirname(os.path.abspath(source))
        path = rst.directives.path(self.arguments[0])
        path = os.path.normpath(os.path.join(source_dir, path))
        path = utils.relative_path(None, path)
        path = str(path)

        # get options (currently not use directive-specific options)
        encoding = self.options.get(
            "encoding", self.state.document.settings.input_encoding
        )
        e_handler = self.state.document.settings.input_encoding_error_handler
        tab_width = self.options.get(
            "tab-width", self.state.document.settings.tab_width
        )

        # open the including file
        try:
            self.state.document.settings.record_dependencies.add(path)
            include_file = io.FileInput(
                source_path=path, encoding=encoding, error_handler=e_handler
            )
        except UnicodeEncodeError as exc:
            raise self.severe(
                f'Problems with "{self.name}" directive path:\n'
                'Cannot encode input file path "{path}" '
                "(wrong locale?)."
            ) from exc
        except IOError as error:
            raise self.severe(
                f'Problems with "{self.name}" directive path:\n{io.error_string(error)}.'
            )

        # read from the file
        startline = self.options.get("start-line", None)
        endline = self.options.get("end-line", None)
        try:
            if startline or (endline is not None):
                lines = include_file.readlines()
                rawtext = "".join(lines[startline:endline])
            else:
                rawtext = include_file.read()
        except UnicodeError as error:
            raise self.severe(
                f'Problem with "{self.name}" directive:\n{io.error_string(error)}'
            )

        config = self.state.document.settings.env.config
        converter = M2R(
            no_underscore_emphasis=config.no_underscore_emphasis,
            parse_relative_links=config.m2r_parse_relative_links,
            anonymous_references=config.m2r_anonymous_references,
            disable_inline_math=config.m2r_disable_inline_math,
            use_mermaid=config.m2r_use_mermaid,
        )
        include_lines = statemachine.string2lines(
            converter(rawtext), tab_width, convert_whitespace=True
        )
        self.state_machine.insert_input(include_lines, path)
        return []


def setup(app):
    """When used for sphinx extension."""
    global _IS_SPHINX  # pylint: disable=global-statement
    _IS_SPHINX = True
    app.add_config_value("no_underscore_emphasis", False, "env")
    app.add_config_value("m2r_parse_relative_links", False, "env")
    app.add_config_value("m2r_anonymous_references", False, "env")
    app.add_config_value("m2r_disable_inline_math", False, "env")
    app.add_config_value(
        "m2r_use_mermaid", "sphinxcontrib.mermaid" in app.config.extensions, "env"
    )
    try:
        app.add_source_parser(".md", M2RParser)  # for older sphinx versions
    except (TypeError, AttributeError):
        app.add_source_suffix(".md", "markdown")
        app.add_source_parser(M2RParser)
    app.add_directive("mdinclude", MdInclude)
    metadata = {
        "version": __version__,
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
    return metadata


def convert(text, **kwargs):
    return M2R(**kwargs)(text)


def parse_from_file(file, encoding="utf-8", **kwargs):
    if not os.path.exists(file):
        raise OSError(f"No such file exists: {file}")
    with _open(file, encoding=encoding) as f:
        src = f.read()
    output = convert(src, **kwargs)
    return output


def save_to_file(file, src, encoding="utf-8", **_kwargs):
    target = os.path.splitext(file)[0] + ".rst"
    if not options.overwrite and os.path.exists(target):  # pylint: disable=no-member
        confirm = input(f"{target} already exists. overwrite it? [y/n]: ")
        if confirm.upper() not in ("Y", "YES"):
            print(f"skip {file}")
            return
    with _open(target, "w", encoding=encoding) as f:
        f.write(src)


def main():
    parse_options()  # parse cli options
    if not options.input_file:  # pylint: disable=no-member
        parser.print_help()
        parser.exit(0)
    for file in options.input_file:  # pylint: disable=no-member
        output = parse_from_file(file)
        if options.dry_run:  # pylint: disable=no-member
            print(output)
        else:
            save_to_file(file, output)


if __name__ == "__main__":
    main()
