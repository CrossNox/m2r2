
Title
=====

SubTitle
--------

**content**

サブタイトル
------------

`A link to GitHub <http://github.com/>`_

This is :math:`E = mc^2` inline math.

This first math :math:`x^2` in this line will render. This one :math:`z^3` should as well.

Also within parentheses (:math:`x^2`) and (:math:`z^3`).

.. code-block:: mermaid

   graph TD;
       A-->B;
       A-->C;
       B-->D;
       C-->D;

Lists
^^^^^

* item one

* item two

  * nested a

  * nested b

* item three

#. first

#. second

#. third

Code and Inline
^^^^^^^^^^^^^^^

Here is ``inline code`` in a sentence.

.. code-block:: python

   def hello():
       print("world")

Image
^^^^^

.. image:: example.png
   :target: example.png
   :alt: example image


Block Quote
^^^^^^^^^^^

..

   This is a quoted paragraph.


Table
^^^^^

.. list-table::
   :header-rows: 1

   * - col1
     - col2
   * - a
     - b
   * - c
     - d


Horizontal Rule
^^^^^^^^^^^^^^^

----

Footnote
^^^^^^^^

This has a footnote\ [#fn-1]_.


.. [#fn-1] The footnote text.
