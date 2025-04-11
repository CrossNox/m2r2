import os
from typing import Any, Dict
from urllib.parse import urlparse

from docutils.utils import column_width
from mistune.core import BlockState
from mistune.renderers.rst import RSTRenderer

_is_sphinx = False


class RestRenderer(RSTRenderer):
    _include_raw_html = False
    # list_indent_re = re.compile(r"^(\s*(#\.|\*)\s)")
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
        # if not _is_sphinx:
        #    parse_options()
        #    if getattr(options, "parse_relative_links", False):
        #        self.parse_relative_links = options.parse_relative_links
        #    if getattr(options, "anonymous_references", False):
        #       self.anonymous_references = options.anonymous_references

    def finalize(self, data):
        return "".join(filter(lambda x: x is not None, data))

    def _indent_block(self, block):
        return "\n".join(
            self.indent + line if line else "" for line in block.splitlines()
        )

    def _raw_html(self, html):
        self._include_raw_html = True
        return rf"\ :raw-html-m2r:`{html}`\ "

    def block_code(self, token: Dict[str, Any], state: BlockState):
        if state == "math":
            first_line = "\n.. math::\n\n"
        elif state == "mermaid" and self.use_mermaid:
            first_line = "\n.. mermaid::\n\n"
        elif state:
            first_line = f"\n.. code-block:: {state}\n\n"
        elif _is_sphinx:
            first_line = "\n::\n\n"
        else:
            first_line = "\n.. code-block::\n\n"
        return first_line + self._indent_block(token) + "\n"

    #     def block_quote(self, token: Dict[str, Any], state: BlockState) -> str:
    #     # text includes some empty line
    #     quote_text = self._indent_block(text.strip("\n"))
    #     return f"\n..\n\n{quote_text}\n\n"

    # def block_text(self, token: Dict[str, Any], state: BlockState) -> str:
    #     return self.render_children(token, state) + "\n"

    # def block_html(self, html):
    #     """Rendering block level pure html content.

    #     :param html: text content of the html snippet.
    #     """
    #     return "\n\n.. raw:: html\n\n" + self._indent_block(html) + "\n\n"

    # def header(self, text, level, raw=None):
    #     """Rendering header/heading tags like ``<h1>`` ``<h2>``.

    #     :param text: rendered text content for the header.
    #     :param level: a number for the header level, for example: 1.
    #     :param raw: raw text content of the header.
    #     """
    #     return f"\n{text}\n{self.hmarks[level] * column_width(text)}\n"

    # def heading(self, text, level, raw=None):
    #     """Rendering header/heading tags like ``<h1>`` ``<h2>``.
    #     :param text: rendered text content for the header.
    #     :param level: a number for the header level, for example: 1.
    #     :param raw: raw text content of the header.
    #     """
    #     return f"\n{text}\n{self.hmarks[level] * column_width(text)}\n"

    # def thematic_break(self):
    #     """Rendering method for ``<hr>`` tag."""
    #     return "\n----\n"

    # def list(self, body, ordered, level, start):
    #     """Rendering list tags like ``<ul>`` and ``<ol>``.

    #     :param body: body contents of the list.
    #     :param ordered: whether this list is ordered or not.
    #     """
    #     mark = "#. " if ordered else "* "
    #     lines = body.splitlines()
    #     for i, line in enumerate(lines):
    #         if line and not line.startswith(self.list_marker):
    #             lines[i] = " " * len(mark) + line

    #     list_lines = "\n".join(lines)
    #     return f"\n{list_lines}\n".replace(self.list_marker, mark)

    # def list_item(self, text, level):
    #     """Rendering list item snippet. Like ``<li>``."""
    #     return "\n" + self.list_marker + text

    # def paragraph(self, text):
    #     """Rendering paragraph tags. Like ``<p>``."""
    #     return "\n" + text + "\n"

    # def table(self, header, body):
    #     """Rendering table element. Wrap header and body in it.

    #     :param header: header part of the table.
    #     :param body: body part of the table.
    #     """
    #     table = "\n.. list-table::\n"
    #     if header and not header.isspace():
    #         table = (
    #             table
    #             + self.indent
    #             + ":header-rows: 1\n\n"
    #             + self._indent_block(header)
    #             + "\n"
    #         )
    #     else:
    #         table = table + "\n"
    #     table = table + self._indent_block(body) + "\n\n"
    #     return table

    # def table_row(self, content):
    #     """Rendering a table row. Like ``<tr>``.

    #     :param content: content of current table row.
    #     """
    #     contents = content.splitlines()
    #     if not contents:
    #         return ""
    #     clist = ["* " + contents[0]]
    #     if len(contents) > 1:
    #         for c in contents[1:]:
    #             clist.append("  " + c)
    #     return "\n".join(clist) + "\n"

    # def table_cell(self, content, **flags):
    #     """Rendering a table cell. Like ``<th>`` ``<td>``.

    #     :param content: content of current table cell.
    #     :param header: whether this is header or not.
    #     :param align: align of current table cell.
    #     """
    #     return "- " + content + "\n"

    # def double_emphasis(self, text):
    #     """Rendering **strong** text.

    #     :param text: text content for emphasis.
    #     """
    #     return rf"\ **{text}**\ "

    # def emphasis(self, text):
    #     """Rendering *emphasis* text.

    #     :param text: text content for emphasis.
    #     """
    #     return rf"\ *{text}*\ "

    # def strong(self, text):
    #     return rf"**{text}**"

    # def codespan(self, text):
    #     """Rendering inline `code` text.

    #     :param text: text content for inline code.
    #     """
    #     if "``" not in text:
    #         return rf"\ ``{text}``\ "
    #     # actually, docutils split spaces in literal
    #     return self._raw_html(
    #         '<code class="docutils literal">'
    #         f'<span class="pre">{text.replace("`", "&#96;")}</span>'
    #         "</code>"
    #     )

    # def linebreak(self):
    #     """Rendering line break like ``<br>``."""
    #     if self.options.get("use_xhtml"):
    #         return self._raw_html("<br />") + "\n"
    #     return self._raw_html("<br>") + "\n"

    # def strikethrough(self, text):
    #     """Rendering ~~strikethrough~~ text.

    #     :param text: text content for strikethrough.
    #     """
    #     return self._raw_html(f"<del>{text}</del>")

    # def text(self, text):
    #     """Rendering unformatted text.

    #     :param text: text content.
    #     """
    #     return text

    # def autolink(self, link, is_email=False):
    #     """Rendering a given link or email address.

    #     :param link: link content or email address.
    #     :param is_email: whether this is an email or not.
    #     """
    #     return link

    # def link(self, link, title, text):
    #     """Rendering a given link with content and title.

    #     :param link: href link for ``<a>`` tag.
    #     :param title: title content for `title` attribute.
    #     :param text: text content for description.
    #     """
    #     if self.anonymous_references:
    #         underscore = "__"
    #     else:
    #         underscore = "_"

    #     if title:
    #         return self._raw_html(f'<a href="{link}" title="{title}">{text}</a>')

    #     if not self.parse_relative_links:
    #         return rf"\ `{text} <{link}>`{underscore}\ "

    #     url_info = urlparse(link)
    #     if url_info.scheme:
    #         return rf"\ `{text} <{link}>`{underscore}\ "

    #     link_type = "doc"
    #     anchor = url_info.fragment
    #     if url_info.fragment:
    #         if url_info.path:
    #             # Can't link to anchors via doc directive.
    #             anchor = ""
    #         else:
    #             # Example: [text](#anchor)
    #             link_type = "ref"
    #     doc_link = f"{os.path.splitext(url_info.path)[0]}{anchor}"
    #     # splittext approach works whether or not path is set. It
    #     # will return an empty string if unset, which leads to
    #     # anchor only ref.
    #     return rf"\ :{link_type}:`{text} <{doc_link}>`\ "

    # def image(self, src, title, text):
    #     """Rendering a image with title and text.

    #     :param src: source link of the image.
    #     :param title: title text of the image.
    #     :param text: alt text of the image.
    #     """
    #     # rst does not support title option
    #     # and I couldn't find title attribute in HTML standard
    #     return "\n".join(
    #         [
    #             "",
    #             f".. image:: {src}",
    #             f"   :target: {src}",
    #             f"   :alt: {text}",
    #             "",
    #         ]
    #     )

    # def inline_html(self, html):
    #     """Rendering span level pure html content.

    #     :param html: text content of the html snippet.
    #     """
    #     return self._raw_html(html)

    # def newline(self):
    #     """Rendering newline element."""
    #     return ""

    # def footnote_ref(self, key, index):
    #     """Rendering the ref anchor of a footnote.

    #     :param key: identity key for the footnote.
    #     :param index: the index count of current footnote.
    #     """
    #     return rf"\ [#fn-{key}]_\ "

    # def footnote_item(self, key, text):
    #     """Rendering a footnote item.

    #     :param key: identity key for the footnote.
    #     :param text: text content of the footnote.
    #     """
    #     return f".. [#fn-{key}] {text.strip()}\n"

    # def footnotes(self, text):
    #     """Wrapper for all footnotes.

    #     :param text: contents of all footnotes.
    #     """
    #     if text:
    #         return "\n\n" + text
    #     return ""

    # # Below outputs are for rst.

    # def image_link(self, url, target, alt):
    #     return "\n".join(
    #         [
    #             "",
    #             f".. image:: {url}",
    #             f"   :target: {target}",
    #             f"   :alt: {alt}",
    #             "",
    #         ]
    #     )

    # def rest_role(self, text):
    #     return text

    # def rest_link(self, text):
    #     return text

    # def inline_math(self, math):
    #     """Extension of recommonmark."""
    #     return rf":math:`{math}`"

    # def eol_literal_marker(self, marker):
    #     """Extension of recommonmark."""
    #     return marker

    def directive(self, text):
        return "\n" + text


# def rest_code_block(self, text):
# return "\n\n"
