from unittest import TestCase, skip

from docutils import io
from docutils.core import Publisher
from docutils.parsers.rst import Parser as RstParser
from docutils.readers.standalone import Reader
from docutils.writers.pseudoxml import Writer

from m2r2 import M2R2, convert
from m2r2.m2r2 import PROLOG


class RendererTestBase(TestCase):
    def conv(self, src, **kwargs):
        out = convert(src, **kwargs)
        self.check_rst(out)
        return out

    def conv_no_check(self, src, **kwargs):
        out = convert(src, **kwargs)
        return out

    def check_rst(self, rst):
        pub = Publisher(
            reader=Reader(),
            parser=RstParser(),
            writer=Writer(),
            source_class=io.StringInput,
            destination_class=io.StringOutput,
        )
        pub.process_programmatic_settings(
            settings_spec=None,
            settings_overrides={"output_encoding": "unicode"},
            config_section=None,
        )
        pub.set_source(rst, source_path=None)
        pub.set_destination(destination=None, destination_path=None)
        output = pub.publish(enable_exit_status=False)
        self.assertLess(pub.document.reporter.max_level, 0)
        return output, pub


class TestBasic(RendererTestBase):
    def test_fail_rst(self):
        with self.assertRaises(AssertionError):
            # This check should be failed and report warning
            self.check_rst("```")

    def test_simple_paragraph(self):
        src = "this is a sentence.\n"
        out = self.conv(src)
        self.assertEqual(out, "\n" + src)

    def test_multiline_paragraph(self):
        src = """\
first sentence.
second sentence."""
        out = self.conv(src)
        self.assertEqual(out, "\n" + src + "\n")

    def test_multi_paragraph(self):
        src = """\
first paragraph.

second paragraph."""
        out = self.conv(src)
        self.assertEqual(out, "\n" + src + "\n")

    def test_hr(self):
        src = """\
a

---

b"""
        out = self.conv(src)
        self.assertEqual(
            out,
            """
a

----

b
""",
        )

    def test_linebreak(self):
        src = "abc def  \nghi"
        out = self.conv(src)
        self.assertEqual(
            out,
            PROLOG
            + """
abc def\\ :raw-html-m2r:`<br>`
ghi"""
            + "\n",
        )


class TestInlineMarkdown(RendererTestBase):
    def test_multiline_emphasis(self):
        src = "*first\nsecond*"
        self.assertEqual(self.conv(src), "\n*first\nsecond*\n")

    def test_multiline_strong(self):
        src = "**first\nsecond**"
        self.assertEqual(self.conv(src), "\n**first\nsecond**\n")

    def test_multiline_emphasis_with_link(self):
        src = "*first\nsecond [link](page) third\nfourth*"
        expected = "\n*first\nsecond* `link <page>`_ *third\nfourth*\n"
        self.assertEqual(self.conv(src), expected)

    def test_multiline_strong_with_code(self):
        src = "**first\nsecond `code` third\nfourth**"
        expected = "\n**first\nsecond** ``code`` **third\nfourth**\n"
        self.assertEqual(self.conv(src), expected)

    def test_url_autolink(self):
        self.assertEqual(self.conv("<https://example.com>"), "\nhttps://example.com\n")

    def test_email_autolink(self):
        self.assertEqual(self.conv("<a@example.com>"), "\na@example.com\n")

    def test_autolink_with_existing_target(self):
        src = """\
<https://example.com>

See `https://example.com`_.

.. _https://example.com: https://other.example"""
        expected = """
https://example.com

See `https://example.com`_.

.. _https://example.com: https://other.example"""
        self.assertEqual(self.conv(src), expected)

    def test_autolink_ignores_reference_options(self):
        self.assertEqual(
            self.conv(
                "<https://example.com> <a@example.com>",
                anonymous_references=True,
                parse_relative_links=True,
            ),
            "\nhttps://example.com a@example.com\n",
        )

    def test_explicit_link_with_url_label(self):
        self.assertEqual(
            self.conv("[https://example.com](https://example.com)"),
            "\n`https://example.com <https://example.com>`_\n",
        )

    def test_link_adjacent_to_text(self):
        self.assertEqual(
            self.conv("prefix[link](https://example.com)suffix"),
            "\nprefix\\ `link <https://example.com>`_\\ suffix\n",
        )

    def test_anonymous_link_adjacent_to_text(self):
        self.assertEqual(
            self.conv(
                "prefix[link](https://example.com)suffix", anonymous_references=True
            ),
            "\nprefix\\ `link <https://example.com>`__\\ suffix\n",
        )

    def test_inline_code(self):
        src = "`a`"
        out = self.conv(src)
        self.assertEqual(out.replace("\n", ""), "``a``")

    def test_inline_code_with_backticks(self):
        src = "```a``a```"
        out = self.conv(src)
        self.assertEqual(
            out.strip(),
            """\
.. role:: raw-html-m2r(raw)
   :format: html


:raw-html-m2r:`<code class="docutils literal"><span class="pre">a&#96;&#96;a</span></code>`""",
        )

    def test_strikethrough(self):
        src = "~~a~~"
        out = self.conv(src)
        self.assertIn(":raw-html-m2r:`<del>a</del>`", out)

    def test_emphasis(self):
        src = "*a*"
        out = self.conv(src)
        self.assertEqual(out.replace("\n", ""), "*a*")

    def test_emphasis_(self):
        src = "_a_"
        out = self.conv(src)
        self.assertEqual(out.replace("\n", ""), "*a*")

    def test_emphasis_no_(self):
        src = "_a_"
        out = self.conv(src, no_underscore_emphasis=True)
        self.assertEqual(out.replace("\n", ""), "_a_")

    def test_double_emphasis(self):
        src = "**a**"
        out = self.conv(src)
        self.assertEqual(out.replace("\n", ""), "**a**")

    def test_double_emphasis__(self):
        src = "__a__"
        out = self.conv(src)
        self.assertEqual(out.replace("\n", ""), "**a**")

    def test_emphasis_no__(self):
        src = "__a__"
        out = self.conv(src, no_underscore_emphasis=True)
        self.assertEqual(out.replace("\n", ""), "__a__")

    def test_autolink(self):
        src = "link to http://example.com/ in sentence."
        out = self.conv(src)
        self.assertEqual(out, "\n" + src + "\n")

    def test_link(self):
        src = "this is a [link](http://example.com/)."
        out = self.conv(src)
        self.assertEqual(out, "\nthis is a `link <http://example.com/>`_.\n")

    def test_anonymous_link(self):
        src = "this is a [link](http://example.com/)."
        out = self.conv(src, anonymous_references=True)
        self.assertEqual(out, "\nthis is a `link <http://example.com/>`__.\n")

    def test_link_with_rel_link_enabled(self):
        src = "this is a [link](http://example.com/)."
        out = self.conv_no_check(src, parse_relative_links=True)
        self.assertEqual(out, "\nthis is a `link <http://example.com/>`_.\n")

    def test_anonymous_link_with_rel_link_enabled(self):
        src = "this is a [link](http://example.com/)."
        out = self.conv_no_check(
            src, parse_relative_links=True, anonymous_references=True
        )
        self.assertEqual(out, "\nthis is a `link <http://example.com/>`__.\n")

    def test_anchor(self):
        src = "this is an [anchor](#anchor)."
        out = self.conv_no_check(src, parse_relative_links=True)
        self.assertEqual(out, "\nthis is an :ref:`anchor <anchor>`.\n")

    def test_relative_link(self):
        src = "this is a [relative link](a_file.md)."
        out = self.conv_no_check(src, parse_relative_links=True)
        self.assertEqual(out, "\nthis is a :doc:`relative link <a_file>`.\n")

    def test_relative_link_with_anchor(self):
        """Anchor is discarded because :doc: cannot target a specific anchor."""
        src = "this is a [relative link](a_file.md#anchor)."
        out = self.conv_no_check(src, parse_relative_links=True)
        self.assertEqual(out, "\nthis is a :doc:`relative link <a_file>`.\n")

    def test_link_title(self):
        src = 'this is a [link](http://example.com/ "example").'
        out = self.conv(src)
        self.assertEqual(
            out,
            """\
.. role:: raw-html-m2r(raw)
   :format: html


this is a :raw-html-m2r:`<a href="http://example.com/" title="example">link</a>`.
""",
        )

    def test_image_link(self):
        src = "[![Alt Text](image_target_url)](link_target_url)"
        out = self.conv(src)
        expected = """
.. image:: image_target_url
   :target: link_target_url
   :alt: Alt Text

"""
        self.assertEqual(out, expected)

    def test_rest_role(self):
        src = "a :code:`some code` inline."
        out = self.conv(src)
        self.assertEqual(out, "\n" + src + "\n")

    def test_rest_role2(self):
        src = "a `some code`:code: inline."
        out = self.conv(src)
        self.assertEqual(out, "\n" + src + "\n")

    def test_rest_link(self):
        src = "a `RefLink <http://example.com>`_ here."
        out = self.conv(src)
        self.assertEqual(out, "\n" + src + "\n")

    def test_rest_link_and_role(self):
        src = "a :code:`a` and `RefLink <http://example.com>`_ here."
        out = self.conv(src)
        self.assertEqual(out, "\n" + src + "\n")

    def test_rest_link_and_role2(self):
        src = "a `a`:code: and `RefLink <http://example.com>`_ here."
        out = self.conv(src)
        self.assertEqual(out, "\n" + src + "\n")

    def test_rest_role_incomplete(self):
        src = "a co:`de` and `RefLink <http://example.com>`_ here."
        out = self.conv(src)
        self.assertEqual(
            out,
            "\na co:\\ ``de`` and `RefLink <http://example.com>`_ here.\n",
        )

    def test_rest_role_incomplete2(self):
        src = "a `RefLink <http://example.com>`_ and co:`de` here."
        out = self.conv(src)
        self.assertEqual(
            out,
            "\na `RefLink <http://example.com>`_ and co:\\ ``de`` here.\n",
        )

    def test_rest_role_with_code(self):
        src = "a `code` and :code:`rest` here."
        out = self.conv(src)
        self.assertEqual(out, "\na ``code`` and :code:`rest` here.\n")

    def test_rest2_role_with_code(self):
        src = "a `code` and `rest`:code: here."
        out = self.conv(src)
        self.assertEqual(out, "\na ``code`` and `rest`:code: here.\n")

    def test_code_with_rest_role(self):
        src = "a :code:`rest` and `code` here."
        out = self.conv(src)
        self.assertEqual(out, "\na :code:`rest` and ``code`` here.\n")

    def test_code_with_rest_role2(self):
        src = "a `rest`:code: and `code` here."
        out = self.conv(src)
        self.assertEqual(out, "\na `rest`:code: and ``code`` here.\n")

    def test_rest_link_with_code(self):
        src = "a `RefLink <a>`_ and `code` here."
        out = self.conv(src)
        self.assertEqual(out, "\na `RefLink <a>`_ and ``code`` here.\n")

    def test_code_with_rest_link(self):
        src = "a `code` and `RefLink <a>`_ here."
        out = self.conv(src)
        self.assertEqual(out, "\na ``code`` and `RefLink <a>`_ here.\n")

    def test_inline_math(self):
        src = "this is `$E = mc^2$` inline math."
        out = self.conv(src)
        self.assertEqual(out, "\nthis is :math:`E = mc^2` inline math.\n")

    def test_disable_inline_math(self):
        src = "this is `$E = mc^2$` inline math."
        out = self.conv(src, disable_inline_math=True)
        self.assertEqual(out, "\nthis is ``$E = mc^2$`` inline math.\n")

    def test_inline_html(self):
        src = "this is <s>html</s>."
        out = self.conv(src)
        self.assertEqual(out, PROLOG + "\nthis is :raw-html-m2r:`<s>html</s>`.\n")

    def test_inline_html_with_colon(self):
        """Inline HTML containing colons must be properly merged."""
        src = "text <b>10:30</b> more"
        out = self.conv(src)
        self.assertIn(":raw-html-m2r:`<b>10:30</b>`", out)

    def test_inline_html_with_backtick(self):
        """Backticks in inline HTML must be escaped to avoid breaking RST role syntax."""
        src = 'text <span title="a`b">hello</span> text'
        out = self.conv(src)
        self.assertIn('title="a&#96;b"', out)

    def test_block_html(self):
        src = "<h1>title</h1>"
        out = self.conv(src)
        self.assertEqual(
            out,
            """
.. raw:: html

   <h1>title</h1>

""",
        )


class TestNoUnderscoreEmphasis(RendererTestBase):
    """Regression tests for no_underscore_emphasis with asterisks."""

    def test_multiline_emphasis(self):
        src = "*first\nsecond* _plain_"
        expected = "\n*first\nsecond* _plain_\n"
        self.assertEqual(self.conv(src, no_underscore_emphasis=True), expected)

    def test_multiline_strong(self):
        src = "**first\nsecond** _plain_"
        expected = "\n**first\nsecond** _plain_\n"
        self.assertEqual(self.conv(src, no_underscore_emphasis=True), expected)

    def test_nested_emphasis(self):
        src = "*a [link](page) and `code`* _plain_"
        expected = "\n*a* `link <page>`_ *and* ``code`` _plain_\n"
        self.assertEqual(self.conv(src, no_underscore_emphasis=True), expected)

    def test_nested_strong(self):
        src = "**a [link](page) and `code`** _plain_"
        expected = "\n**a** `link <page>`_ **and** ``code`` _plain_\n"
        self.assertEqual(self.conv(src, no_underscore_emphasis=True), expected)

    def test_nested_emphasis_after_text(self):
        src = "prefix *a [link](page) and `code`* _plain_"
        expected = "\nprefix *a* `link <page>`_ *and* ``code`` _plain_\n"
        self.assertEqual(self.conv(src, no_underscore_emphasis=True), expected)

    def test_nested_strong_after_text(self):
        src = "prefix **a [link](page) and `code`** _plain_"
        expected = "\nprefix **a** `link <page>`_ **and** ``code`` _plain_\n"
        self.assertEqual(self.conv(src, no_underscore_emphasis=True), expected)

    def test_asterisk_emphasis(self):
        src = "*hello*"
        out = self.conv(src, no_underscore_emphasis=True)
        self.assertEqual(out.replace("\n", ""), "*hello*")

    def test_asterisk_strong(self):
        src = "**hello**"
        out = self.conv(src, no_underscore_emphasis=True)
        self.assertEqual(out.replace("\n", ""), "**hello**")

    def test_underscore_emphasis_passthrough(self):
        src = "_hello_"
        out = self.conv(src, no_underscore_emphasis=True)
        self.assertEqual(out.replace("\n", ""), "_hello_")

    def test_underscore_strong_passthrough(self):
        src = "__hello__"
        out = self.conv(src, no_underscore_emphasis=True)
        self.assertEqual(out.replace("\n", ""), "__hello__")

    def test_mixed_emphasis_in_sentence(self):
        src = "This has *emphasis* and _underscored_ text."
        out = self.conv(src, no_underscore_emphasis=True)
        self.assertIn("*emphasis*", out)
        self.assertIn("_underscored_", out)
        self.assertNotIn("*underscored*", out)


class TestBlockQuote(RendererTestBase):
    def test_block_quote(self):
        src = """\
> q1
> q2"""
        out = self.conv(src)
        self.assertEqual(
            out,
            """
..

   q1
   q2

""",
        )

    def test_block_quote_nested(self):
        src = """\
> q1
> > q2"""
        out = self.conv(src)
        # one extra empty line is inserted, but still valid rst anyway
        self.assertEqual(
            out,
            """
..

   q1

   ..

      q2

""",
        )

    @skip("markdown does not support dedent in block quote")
    def test_block_quote_nested_2(self):
        src = """\
> q1
> > q2
> q3"""
        out = self.conv(src)
        self.assertEqual(
            out,
            """
..

   q1

   ..
      q2

   q3

""",
        )


class TestCodeBlock(RendererTestBase):
    def test_plain_code_block(self):
        src = """\
```
pip install sphinx
```"""
        out = self.conv(src)
        self.assertEqual(out, "\n.. code-block::\n\n   pip install sphinx\n")

    def test_plain_code_block_tilda(self):
        src = """\
~~~
pip install sphinx
~~~"""
        out = self.conv(src)
        self.assertEqual(out, "\n.. code-block::\n\n   pip install sphinx\n")

    def test_code_block_math(self):
        src = """\
```math
E = mc^2
```"""
        out = self.conv(src)
        self.assertEqual(
            out,
            """
.. math::

   E = mc^2
""",
        )

    def test_plain_code_block_indent(self):
        src = """\
```
pip install sphinx
    new line
```"""
        out = self.conv(src)
        self.assertEqual(
            out, "\n.. code-block::\n\n   pip install sphinx\n       new line\n"
        )

    def test_python_code_block(self):
        src = """\
```python
print(1)
```"""
        out = self.conv(src)
        self.assertEqual(
            out,
            """
.. code-block:: python

   print(1)
""",
        )

    def test_python_code_block_indent(self):
        src = """\
```python
def a(i):
    print(i)
```"""
        out = self.conv(src)
        self.assertEqual(
            out,
            """
.. code-block:: python

   def a(i):
       print(i)
""",
        )

    def test_code_block_info_string_extra_text(self):
        """Info string with extra metadata should use only the language name."""
        src = """\
```python title=test
print(1)
```"""
        out = self.conv(src)
        self.assertEqual(
            out,
            """
.. code-block:: python

   print(1)
""",
        )


class TestImage(RendererTestBase):
    def test_image_destination_and_alt(self):
        for source in [
            '''\
![alt][img]

[img]: image.png "Title"''',
            """\
![alt][]

[alt]: image.png""",
            """\
![alt]

[alt]: image.png""",
            '![alt](image.png "Title")',
            "![alt](image.png 'Title')",
        ]:
            with self.subTest(source=source):
                expected = """
.. image:: image.png
   :target: image.png
   :alt: alt

"""
                self.assertEqual(self.conv(source), expected)

    def test_standalone_image(self):
        source = """\
![A](a.png)

* ![A](a.png)

> ![A](a.png)
"""
        expected = """
.. image:: a.png
   :target: a.png
   :alt: A


* .. image:: a.png
     :target: a.png
     :alt: A

..

   .. image:: a.png
      :target: a.png
      :alt: A

"""
        self.assertEqual(self.conv(source), expected)

    def test_standalone_linked_image(self):
        source = """\
[![A](a.png)](page.html)

* [![A](a.png)](page.html)

> [![A](a.png)](page.html)
"""
        expected = """
.. image:: a.png
   :target: page.html
   :alt: A


* .. image:: a.png
     :target: page.html
     :alt: A

..

   .. image:: a.png
      :target: page.html
      :alt: A

"""
        self.assertEqual(self.conv(source), expected)

    def test_standalone_reference_image(self):
        source = """\
![A][img]

* ![A][img]

> ![A][img]

[img]: a.png
"""
        expected = """
.. image:: a.png
   :target: a.png
   :alt: A


* .. image:: a.png
     :target: a.png
     :alt: A

..

   .. image:: a.png
      :target: a.png
      :alt: A

"""
        self.assertEqual(self.conv(source), expected)

    def test_standalone_linked_reference_image(self):
        source = """\
[![A][img]](page.html)

* [![A][img]](page.html)

> [![A][img]](page.html)

[img]: a.png
"""
        expected = """
.. image:: a.png
   :target: page.html
   :alt: A


* .. image:: a.png
     :target: page.html
     :alt: A

..

   .. image:: a.png
      :target: page.html
      :alt: A

"""
        self.assertEqual(self.conv(source), expected)

    def test_inline_image(self):
        source = """\
# ![A](a.png)

before ![A](a.png) after

* before ![A](a.png) after
"""
        expected = """
.. |m2r-image-d79de0460ffb1b7efdeb0bfe4f3b6e4c429069f843367cfd6d95707acdd35407| image:: a.png
   :target: a.png
   :alt: A


|m2r-image-d79de0460ffb1b7efdeb0bfe4f3b6e4c429069f843367cfd6d95707acdd35407|
================================================================================

before |m2r-image-d79de0460ffb1b7efdeb0bfe4f3b6e4c429069f843367cfd6d95707acdd35407| after

* before |m2r-image-d79de0460ffb1b7efdeb0bfe4f3b6e4c429069f843367cfd6d95707acdd35407| after
"""
        self.assertEqual(self.conv(source), expected)

    def test_inline_linked_image(self):
        source = """\
# [![A](a.png)](page.html)

before [![A](a.png)](page.html) after

* before [![A](a.png)](page.html) after
"""
        expected = """
.. |m2r-image-ed8a5249f9ad19b20ee01ce38776d98f869cdc5200888bce5bc2d9985510d8ed| image:: a.png
   :target: page.html
   :alt: A


|m2r-image-ed8a5249f9ad19b20ee01ce38776d98f869cdc5200888bce5bc2d9985510d8ed|
================================================================================

before |m2r-image-ed8a5249f9ad19b20ee01ce38776d98f869cdc5200888bce5bc2d9985510d8ed| after

* before |m2r-image-ed8a5249f9ad19b20ee01ce38776d98f869cdc5200888bce5bc2d9985510d8ed| after
"""
        self.assertEqual(self.conv(source), expected)

    def test_image(self):
        src = "![alt text](a.png)"
        out = self.conv(src)
        self.assertEqual(
            out,
            """
.. image:: a.png
   :target: a.png
   :alt: alt text

""",
        )

    def test_image_title(self):
        src = '![alt text](a.png "title")'
        out = self.conv(src)
        # title is not supported by RST image directive, but image should still render
        self.assertEqual(
            out,
            """
.. image:: a.png
   :target: a.png
   :alt: alt text

""",
        )


class TestHeading(RendererTestBase):
    def test_heading(self):
        src = "# head 1"
        out = self.conv(src)
        self.assertEqual(out, "\nhead 1\n" + "=" * 6 + "\n")

    def test_heading_multibyte(self):
        src = "# マルチバイト文字\n"
        out = self.conv(src)
        self.assertEqual(out, "\nマルチバイト文字\n" + "=" * 16 + "\n")

    def test_heading_level_2(self):
        src = "## head 2"
        out = self.conv(src)
        self.assertEqual(out, "\nhead 2\n" + "-" * 6 + "\n")

    def test_heading_level_3(self):
        src = "### head 3"
        out = self.conv(src)
        self.assertEqual(out, "\nhead 3\n" + "^" * 6 + "\n")

    def test_heading_level_4(self):
        src = "#### head 4"
        out = self.conv(src)
        self.assertEqual(out, "\nhead 4\n" + "~" * 6 + "\n")

    def test_heading_level_5(self):
        src = "##### head 5"
        out = self.conv(src)
        self.assertEqual(out, "\nhead 5\n" + '"' * 6 + "\n")

    def test_heading_level_6(self):
        src = "###### head 6"
        out = self.conv(src)
        self.assertEqual(out, "\nhead 6\n" + "#" * 6 + "\n")


class TestList(RendererTestBase):
    def test_unordered_list_item_preserves_blocks(self):
        source = """\
* first paragraph

  second paragraph

  ```python
  print(1)
  ```
"""
        expected = """
* first paragraph

  second paragraph

  .. code-block:: python

     print(1)
"""
        self.assertEqual(self.conv(source), expected)

    def test_ordered_list_item_preserves_blocks(self):
        source = """\
1. first paragraph

   second paragraph

   ```python
   print(1)
   ```
"""
        expected = """
#. first paragraph

   second paragraph

   .. code-block:: python

      print(1)
"""
        self.assertEqual(self.conv(source), expected)

    def test_wide_ordered_list_item_preserves_blocks(self):
        source = """\
10. first paragraph

    second paragraph

    ```python
    print(1)
    ```
"""
        expected = """
#. first paragraph

   second paragraph

   .. code-block:: python

      print(1)
"""
        self.assertEqual(self.conv(source), expected)

    def test_list_preserves_content_after_nested_list(self):
        source = """\
* parent

  * child

  after child

* next"""
        expected = """
* parent

  * child

  after child

* next
"""
        self.assertEqual(self.conv(source), expected)

    def test_list_preserves_lazy_continuation(self):
        source = """\
* first
continued

outside"""
        expected = """
* first
  continued

outside
"""
        self.assertEqual(self.conv(source), expected)

    def test_thematic_break_after_list(self):
        source = """\
* item

* * *

after"""
        expected = """
* item

----

after
"""
        self.assertEqual(self.conv(source), expected)

    def test_ul(self):
        src = "* list"
        out = self.conv(src)
        self.assertEqual(out, "\n* list\n")

    def test_ol(self):
        src = "1. list"
        out = self.conv(src)
        self.assertEqual(out, "\n#. list\n")

    def test_nested_ul(self):
        src = """\
* list 1
* list 2
  * list 2.1
  * list 2.2
* list 3"""
        out = self.conv(src)
        self.assertEqual(
            out,
            "\n* list 1\n* list 2\n\n  * list 2.1\n  * list 2.2\n\n* list 3\n",
        )

    def test_nested_ul_2(self):
        src = """\
* list 1
* list 2
  * list 2.1
  * list 2.2
    * list 2.2.1
    * list 2.2.2
* list 3"""
        out = self.conv(src)
        expected = """\

* list 1
* list 2

  * list 2.1
  * list 2.2

    * list 2.2.1
    * list 2.2.2

* list 3
"""
        self.assertEqual(out, expected)

    def test_nested_ol(self):
        src = """\
1. list 1
2. list 2
  2. list 2.1
  3. list 2.2
3. list 3"""
        out = self.conv(src)
        expected = """\

#. list 1
#. list 2

   #. list 2.1
   #. list 2.2

#. list 3
"""
        self.assertEqual(out, expected)

    def test_nested_ol_2(self):
        src = """\
1. list 1
2. list 2
  3. list 2.1
  4. list 2.2
    5. list 2.2.1
    6. list 2.2.2
7. list 3"""
        out = self.conv(src)
        expected = """\

#. list 1
#. list 2

   #. list 2.1
   #. list 2.2

      #. list 2.2.1
      #. list 2.2.2

#. list 3
"""
        self.assertEqual(out, expected)

    def test_nested_mixed_1(self):
        src = """1. list 1
2. list 2
  * list 2.1
  * list 2.2
    1. list 2.2.1
    2. list 2.2.2
7. list 3"""

        expected = """\

#. list 1
#. list 2

   * list 2.1
   * list 2.2

     #. list 2.2.1
     #. list 2.2.2

#. list 3
"""

        out = self.conv(src)
        self.assertEqual(out, expected)

    def test_nested_multiline_1(self):
        src = """\
* list 1
  list 1 cont
* list 2
  list 2 cont
  * list 2.1
    list 2.1 cont
  * list 2.2
    list 2.2 cont
    * list 2.2.1
    * list 2.2.2
* list 3"""
        out = self.conv(src)
        expected = """\

* list 1
  list 1 cont
* list 2
  list 2 cont

  * list 2.1
    list 2.1 cont
  * list 2.2
    list 2.2 cont

    * list 2.2.1
    * list 2.2.2

* list 3
"""
        self.assertEqual(out, expected)

    def test_nested_multiline_2(self):
        src = """\
1. list 1
  list 1 cont
1. list 2
  list 2 cont
  1. list 2.1
    list 2.1 cont
  1. list 2.2
    list 2.2 cont
    1. list 2.2.1
    1. list 2.2.2
1. list 3"""
        out = self.conv(src)
        expected = """\

#. list 1
   list 1 cont
#. list 2
   list 2 cont

   #. list 2.1
      list 2.1 cont
   #. list 2.2
      list 2.2 cont

      #. list 2.2.1
      #. list 2.2.2

#. list 3
"""
        self.assertEqual(out, expected)

    def test_nested_multiline_3(self):
        src = """\
1. list 1
  list 1 cont
1. list 2
  list 2 cont
  * list 2.1
    list 2.1 cont
  * list 2.2
    list 2.2 cont
    1. list 2.2.1
    1. list 2.2.2
1. list 3"""
        out = self.conv(src)
        expected = """\

#. list 1
   list 1 cont
#. list 2
   list 2 cont

   * list 2.1
     list 2.1 cont
   * list 2.2
     list 2.2 cont

     #. list 2.2.1
     #. list 2.2.2

#. list 3
"""
        self.assertEqual(out, expected)

    def test_inline_markup_in_list(self):
        """Inline markup (code spans, emphasis, links) must be parsed in list items."""
        src = """\
* plain text
* text with ``code`` here
* text with *emphasis* here
* text with [link](http://example.com) here"""
        out = self.conv(src)
        self.assertIn("``code``", out)
        self.assertIn("*emphasis*", out)
        self.assertIn("`link <http://example.com>`_", out)

    def test_codespan_with_role_in_list(self):
        """Code spans containing RST role syntax must not break docutils."""
        src = "* support backticks (`` `text`:role: style``)"
        out = self.conv(src)
        # The backtick-role content must be rendered as inline literal
        self.assertIn("```text`:role: style``", out)


class TestComplexText(RendererTestBase):
    def test_code(self):
        src = """
some sentence
```python
print(1)
```
some sentence

# title
```python
print(1)
```
---
end
"""
        out = self.conv(src)
        self.assertIn(".. code-block:: python", out)
        self.assertIn("print(1)", out)
        self.assertIn(
            """\
title
=====""",
            out,
        )
        self.assertIn("----", out)
        self.assertIn("end", out)


class TestTable(RendererTestBase):
    def test_issue_75_table_images(self):
        source = """\
| A | B |
|---|---|
| ![A](a.png) | ![B](b.png) |
"""
        expected = """
.. |m2r-image-d79de0460ffb1b7efdeb0bfe4f3b6e4c429069f843367cfd6d95707acdd35407| image:: a.png
   :target: a.png
   :alt: A

.. |m2r-image-bf1518c471859b05778affe29630c3ac0d5ccaca3c88d107e5df2e98c8224bc0| image:: b.png
   :target: b.png
   :alt: B


.. list-table::
   :header-rows: 1

   * - A
     - B
   * - |m2r-image-d79de0460ffb1b7efdeb0bfe4f3b6e4c429069f843367cfd6d95707acdd35407|\\
     - |m2r-image-bf1518c471859b05778affe29630c3ac0d5ccaca3c88d107e5df2e98c8224bc0|\\

"""
        self.assertEqual(self.conv(source), expected)

    def test_issue_75_table_mixed_image(self):
        source = """\
| A | B |
|---|---|
| before ![A](a.png) after | ![B](b.png) |
"""
        expected = """
.. |m2r-image-d79de0460ffb1b7efdeb0bfe4f3b6e4c429069f843367cfd6d95707acdd35407| image:: a.png
   :target: a.png
   :alt: A

.. |m2r-image-bf1518c471859b05778affe29630c3ac0d5ccaca3c88d107e5df2e98c8224bc0| image:: b.png
   :target: b.png
   :alt: B


.. list-table::
   :header-rows: 1

   * - A
     - B
   * - before |m2r-image-d79de0460ffb1b7efdeb0bfe4f3b6e4c429069f843367cfd6d95707acdd35407| after
     - |m2r-image-bf1518c471859b05778affe29630c3ac0d5ccaca3c88d107e5df2e98c8224bc0|\\

"""
        self.assertEqual(self.conv(source), expected)

    def test_issue_75_table_linked_image(self):
        source = """\
| A | B |
|---|---|
| [![A](a.png)](https://example.com) | ![B](b.png) |
"""
        expected = """
.. |m2r-image-486be93246348dc82e02a910d343c83464a6469569cc19e8098719a2d93f9016| image:: a.png
   :target: https://example.com
   :alt: A

.. |m2r-image-bf1518c471859b05778affe29630c3ac0d5ccaca3c88d107e5df2e98c8224bc0| image:: b.png
   :target: b.png
   :alt: B


.. list-table::
   :header-rows: 1

   * - A
     - B
   * - |m2r-image-486be93246348dc82e02a910d343c83464a6469569cc19e8098719a2d93f9016|\\
     - |m2r-image-bf1518c471859b05778affe29630c3ac0d5ccaca3c88d107e5df2e98c8224bc0|\\

"""
        self.assertEqual(self.conv(source), expected)

    def test_issue_75_table_reference_image(self):
        source = """\
| A | B |
|---|---|
| ![A][img] | ![B](b.png) |

[img]: a.png
"""
        expected = """
.. |m2r-image-d79de0460ffb1b7efdeb0bfe4f3b6e4c429069f843367cfd6d95707acdd35407| image:: a.png
   :target: a.png
   :alt: A

.. |m2r-image-bf1518c471859b05778affe29630c3ac0d5ccaca3c88d107e5df2e98c8224bc0| image:: b.png
   :target: b.png
   :alt: B


.. list-table::
   :header-rows: 1

   * - A
     - B
   * - |m2r-image-d79de0460ffb1b7efdeb0bfe4f3b6e4c429069f843367cfd6d95707acdd35407|\\
     - |m2r-image-bf1518c471859b05778affe29630c3ac0d5ccaca3c88d107e5df2e98c8224bc0|\\

"""
        self.assertEqual(self.conv(source), expected)

    def test_table(self):
        src = """\
h1 | h2 | h3
--- | --- | ---
1 | 2 | 3
4 | 5 | 6"""
        out = self.conv(src)
        expected = """
.. list-table::
   :header-rows: 1

   * - h1
     - h2
     - h3
   * - 1
     - 2
     - 3
   * - 4
     - 5
     - 6

"""
        self.assertEqual(out, expected)


class TestFootNote(RendererTestBase):
    def test_footnote(self):
        src = """\
This is a[^1] footnote[^2] ref[^ref] with rst [#a]_.

[^1]: note 1
[^2]: note 2
[^ref]: note ref
.. [#a] note rst"""
        out = self.conv(src)
        expected = """
This is a\\ [#fn-1]_ footnote\\ [#fn-2]_ ref\\ [#fn-ref]_ with rst [#a]_.

.. [#a] note rst

.. [#fn-1] note 1
.. [#fn-2] note 2
.. [#fn-ref] note ref
"""
        self.assertEqual(out, expected)

    def test_footnote_mixed_case(self):
        """Footnote references with mixed case should be normalized to lowercase."""
        src = """\
This has a[^MyRef] footnote.

[^MyRef]: mixed case note"""
        out = self.conv(src)
        # Both the reference and definition should use lowercase
        self.assertIn("[#fn-myref]_", out)
        self.assertIn(".. [#fn-myref]", out)

    def test_sphinx_ref(self):
        src = """\
This is a sphinx [ref]_ global ref.

.. [ref] ref text"""
        out = self.conv(src)
        self.assertEqual(out, "\n" + src)


class TestDirective(RendererTestBase):
    def test_comment_oneline(self):
        src = ".. a"
        out = self.conv(src)
        self.assertEqual(out, "\n.. a")

    def test_comment_indented(self):
        src = "    .. a"
        out = self.conv(src)
        self.assertEqual(out, "\n    .. a")

    def test_comment_newline(self):
        src = """\
..

   comment

newline"""
        out = self.conv(src)
        self.assertEqual(
            out,
            """
..

   comment

newline
""",
        )

    def test_comment_multiline(self):
        comment = """\
.. this is comment.
   this is also comment.


    comment may include empty line.


"""
        src = comment + "`eoc`"
        out = self.conv(src)
        self.assertEqual(out, "\n" + comment + "``eoc``\n")


class TestRestCode(RendererTestBase):
    def test_rest_code_block_empty(self):
        src = "\n\n::\n\n"
        out = self.conv(src)
        self.assertEqual(out, "\n")

    def test_eol_marker(self):
        src = """\
a::

    code
"""
        out = self.conv(src)
        self.assertEqual(
            out,
            """
a:

.. code-block::

   code
""",
        )

    def test_eol_marker_remove(self):
        src = """\
a ::

    code
"""
        out = self.conv(src)
        self.assertEqual(
            out,
            """
a

.. code-block::

   code
""",
        )


class TestMermaid(RendererTestBase):
    def test_mermaid_code_block(self):
        src = """\
```mermaid
graph TD
    A --> B
```"""
        # conv_no_check: docutils doesn't know the mermaid directive
        out = self.conv_no_check(src, use_mermaid=True)
        self.assertEqual(
            out,
            """
.. mermaid::

   graph TD
       A --> B
""",
        )

    def test_mermaid_disabled(self):
        src = """\
```mermaid
graph TD
    A --> B
```"""
        # conv_no_check: Pygments has no mermaid lexer
        out = self.conv_no_check(src)
        self.assertEqual(
            out,
            """
.. code-block:: mermaid

   graph TD
       A --> B
""",
        )


class TestRawHtmlProlog(RendererTestBase):
    def test_prolog_not_added_without_html(self):
        src = "plain text"
        out = self.conv(src)
        self.assertNotIn("raw-html-m2r", out)

    def test_prolog_added_with_inline_html(self):
        src = "text <b>bold</b> text"
        out = self.conv(src)
        self.assertIn(".. role:: raw-html-m2r(raw)", out)
        self.assertIn(":raw-html-m2r:", out)

    def test_prolog_not_sticky_across_calls(self):
        """Ensure raw HTML in one document doesn't leak PROLOG into the next."""
        converter = M2R2()
        out1 = converter("text <b>bold</b> text")
        self.assertIn("raw-html-m2r", out1)
        out2 = converter("plain text")
        self.assertNotIn("raw-html-m2r", out2)


class TestEdgeCases(RendererTestBase):
    def test_empty_input(self):
        out = self.conv("")
        # Should produce minimal output without errors
        self.assertEqual(out.strip(), "")

    def test_whitespace_only_input(self):
        out = self.conv("\n")
        self.assertEqual(out.strip(), "")

    def test_whitespace_multiple_newlines(self):
        out = self.conv("\n\n\n")
        self.assertEqual(out.strip(), "")


class TestInstanceReuse(RendererTestBase):
    """Verify that converting multiple documents via a single M2R2 instance
    does not leak state between calls."""

    def test_inline_image_definitions_do_not_leak_between_calls(self):
        converter = M2R2()
        source = """\
# ![A](a.png)

before ![A](a.png) after

* before ![A](a.png) after
"""
        expected = """
.. |m2r-image-d79de0460ffb1b7efdeb0bfe4f3b6e4c429069f843367cfd6d95707acdd35407| image:: a.png
   :target: a.png
   :alt: A


|m2r-image-d79de0460ffb1b7efdeb0bfe4f3b6e4c429069f843367cfd6d95707acdd35407|
================================================================================

before |m2r-image-d79de0460ffb1b7efdeb0bfe4f3b6e4c429069f843367cfd6d95707acdd35407| after

* before |m2r-image-d79de0460ffb1b7efdeb0bfe4f3b6e4c429069f843367cfd6d95707acdd35407| after
"""
        self.assertEqual(converter(source), expected)
        self.assertEqual(converter("plain text"), "\nplain text\n")

    def test_list_state_does_not_leak(self):
        converter = M2R2()
        out1 = converter("""\
* item a
* item b
""")
        self.assertIn("* item a", out1)
        out2 = converter("plain paragraph\n")
        # The second document should be a plain paragraph with no list markers
        self.assertNotIn("*", out2.strip())
        self.assertIn("plain paragraph", out2)

    def test_table_then_paragraph(self):
        converter = M2R2()
        out1 = converter("""\
h1 | h2
--- | ---
1 | 2
""")
        self.assertIn("list-table", out1)
        out2 = converter("just text\n")
        self.assertNotIn("list-table", out2)
        self.assertIn("just text", out2)

    def test_footnote_then_plain(self):
        converter = M2R2()
        out1 = converter("""\
Text[^1].

[^1]: note
""")
        self.assertIn("[#fn-1]", out1)
        out2 = converter("no footnotes here\n")
        self.assertNotIn("[#fn", out2)
        self.assertIn("no footnotes here", out2)
