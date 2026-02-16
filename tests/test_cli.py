"""Tests for the m2r2 CLI."""

import subprocess
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from m2r2.cli.m2r2 import main, parse_from_file

curdir = Path(__file__).parent
test_md = curdir / "test.md"
test_rst = curdir / "test.rst"


class TestConvert(TestCase):
    def setUp(self):
        self._orig_rst = test_rst.read_text() if test_rst.exists() else None

    def tearDown(self):
        if self._orig_rst is not None:
            test_rst.write_text(self._orig_rst)
        elif test_rst.exists():
            test_rst.unlink()

    def test_no_file(self):
        p = subprocess.Popen(
            ["m2r2"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        p.wait()
        self.assertEqual(p.returncode, 2)
        assert p.stderr is not None
        message = p.stderr.read().decode()
        self.assertIn("usage", message)
        self.assertIn("required: FILE", message)

    def test_parse_file(self):
        output = parse_from_file(test_md)
        expected = test_rst.read_text()
        self.assertEqual(output.strip(), expected.strip())

    def test_dryrun(self):
        rst = test_rst.read_text()
        test_rst.unlink()
        self.assertFalse(test_rst.exists())
        with patch("builtins.print") as m:
            main(["--dry-run", str(test_md)])
        self.assertFalse(test_rst.exists())
        m.assert_called_once_with(rst)

    def test_write_file(self):
        test_rst.unlink()
        self.assertFalse(test_rst.exists())
        main([str(test_md)])
        self.assertTrue(test_rst.exists())

    def test_overwrite_file(self):
        test_rst.write_text("test")
        first_line = test_rst.read_text().splitlines()[0]
        self.assertIn("test", first_line)
        with patch("builtins.input", return_value="y"):
            main([str(test_md)])
        self.assertTrue(test_rst.exists())
        first_line = test_rst.read_text().splitlines()[0]
        self.assertNotIn("test", first_line)

    def test_overwrite_option(self):
        test_rst.write_text("test")
        first_line = test_rst.read_text().splitlines()[0]
        self.assertIn("test", first_line)
        with patch("builtins.input", return_value="y") as m_input:
            with patch("builtins.print") as m_print:
                main(["--overwrite", str(test_md)])
        self.assertTrue(test_rst.exists())
        self.assertFalse(m_input.called)
        self.assertFalse(m_print.called)
        first_line = test_rst.read_text().splitlines()[0]
        self.assertNotIn("test", first_line)

    def test_underscore_option(self):
        with patch("builtins.print") as m:
            main(["--no-underscore-emphasis", "--dry-run", str(test_md)])
        self.assertIn("__content__", m.call_args[0][0])
        self.assertNotIn("**content**", m.call_args[0][0])

    def test_anonymous_reference_option(self):
        with patch("builtins.print") as m:
            main(["--anonymous-references", "--dry-run", str(test_md)])
        self.assertIn("`A link to GitHub <http://github.com/>`__", m.call_args[0][0])

    def test_disable_inline_math(self):
        with patch("builtins.print") as m:
            main(["--disable-inline-math", "--dry-run", str(test_md)])
        self.assertIn("``$E = mc^2$``", m.call_args[0][0])
        self.assertNotIn(":math:", m.call_args[0][0])

    def test_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            parse_from_file("nonexistent.md")

    def test_decline_overwrite(self):
        test_rst.write_text("original")
        with patch("builtins.input", return_value="n"):
            with patch("builtins.print") as m_print:
                main([str(test_md)])
        self.assertEqual(test_rst.read_text(), "original")
        m_print.assert_called_once_with(f"Skipping {test_md}")
