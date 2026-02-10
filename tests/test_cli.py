#!/usr/bin/env python3

import subprocess
import sys
from copy import copy
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from m2r2.cli.m2r2 import main, options, parse_from_file

curdir = Path(__file__).parent
test_md = curdir / "test.md"
test_rst = curdir / "test.rst"


class TestConvert(TestCase):
    def setUp(self):
        # reset cli options
        options.overwrite = False
        options.dry_run = False
        options.no_underscore_emphasis = False
        options.anonymous_references = False
        options.disable_inline_math = False
        self._orig_argv = copy(sys.argv)
        if test_rst.exists():
            self._orig_rst = test_rst.read_text()

    def tearDown(self):
        sys.argv = self._orig_argv
        test_rst.write_text(self._orig_rst)

    def test_no_file(self):
        p = subprocess.Popen(
            [sys.executable, "-m", "m2r2"],
            stdout=subprocess.PIPE,
        )
        p.wait()
        self.assertEqual(p.returncode, 0)
        with p.stdout as buffer:
            message = buffer.read().decode()
        self.assertIn("usage", message)
        self.assertIn("underscore-emphasis", message)
        self.assertIn("anonymous-references", message)
        self.assertIn("inline-math", message)
        self.assertRegex(message, r"option(s|al arguments):")

    def test_parse_file(self):
        output = parse_from_file(test_md)
        expected = test_rst.read_text()
        self.assertEqual(output.strip(), expected.strip())

    def test_dryrun(self):
        sys.argv = [sys.argv[0], "--dry-run", str(test_md)]
        rst = test_rst.read_text()
        test_rst.unlink()
        self.assertFalse(test_rst.exists())
        with patch("builtins.print") as m:
            main()
        self.assertFalse(test_rst.exists())
        m.assert_called_once_with(rst)

    def test_write_file(self):
        sys.argv = [sys.argv[0], str(test_md)]
        test_rst.unlink()
        self.assertFalse(test_rst.exists())
        main()
        self.assertTrue(test_rst.exists())

    def test_overwrite_file(self):
        sys.argv = [sys.argv[0], str(test_md)]
        test_rst.write_text("test")
        first_line = test_rst.read_text().splitlines()[0]
        self.assertIn("test", first_line)
        with patch("builtins.input", return_value="y"):
            main()
        self.assertTrue(test_rst.exists())
        first_line = test_rst.read_text().splitlines()[0]
        self.assertNotIn("test", first_line)

    def test_overwrite_option(self):
        sys.argv = [sys.argv[0], "--overwrite", str(test_md)]
        test_rst.write_text("test")
        first_line = test_rst.read_text().splitlines()[0]
        self.assertIn("test", first_line)
        with patch("builtins.input", return_value="y") as m_input:
            with patch("builtins.print") as m_print:
                main()
        self.assertTrue(test_rst.exists())
        self.assertFalse(m_input.called)
        self.assertFalse(m_print.called)
        first_line = test_rst.read_text().splitlines()[0]
        self.assertNotIn("test", first_line)

    def test_underscore_option(self):
        sys.argv = [sys.argv[0], "--no-underscore-emphasis", "--dry-run", str(test_md)]
        with patch("builtins.print") as m:
            main()
        self.assertIn("__content__", m.call_args[0][0])
        self.assertNotIn("**content**", m.call_args[0][0])

    def test_anonymous_reference_option(self):
        sys.argv = [sys.argv[0], "--anonymous-references", "--dry-run", str(test_md)]
        with patch("builtins.print") as m:
            main()
        self.assertIn("`A link to GitHub <http://github.com/>`__", m.call_args[0][0])

    def test_disable_inline_math(self):
        sys.argv = [sys.argv[0], "--disable-inline-math", "--dry-run", str(test_md)]
        with patch("builtins.print") as m:
            main()
        self.assertIn("``$E = mc^2$``", m.call_args[0][0])
        self.assertNotIn(":math:", m.call_args[0][0])
