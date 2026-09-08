"""Tests for the m2r2 CLI."""

import subprocess
import sys
import tempfile
from io import StringIO
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from m2r2.cli.m2r2 import main, parse_from_file

curdir = Path(__file__).parent
test_md = curdir / "test.md"
test_rst = curdir / "test.rst"


class TestConvert(TestCase):
    """CLI conversion tests.

    Tests that write files use a temporary directory so the real
    ``tests/test.rst`` fixture is never mutated.
    """

    def _copy_to_tmp(self, tmpdir: Path) -> tuple[Path, Path]:
        """Copy test.md into *tmpdir* and return (md_path, expected_rst_path)."""
        md = tmpdir / "test.md"
        md.write_text(test_md.read_text())
        return md, tmpdir / "test.rst"

    def test_no_file(self):
        p = subprocess.Popen(
            [sys.executable, "-m", "m2r2"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        p.wait()
        self.assertEqual(p.returncode, 2)
        assert p.stderr is not None
        message = p.stderr.read().decode()
        self.assertIn("usage", message)
        self.assertIn("required: FILE", message)

    def test_missing_file_via_main(self):
        """Missing files are reported to stderr and cause exit code 1."""
        with self.assertRaises(SystemExit) as ctx:
            main(["nonexistent.md"])
        self.assertEqual(ctx.exception.code, 1)

    def test_missing_file_via_parse_from_file(self):
        with self.assertRaises(FileNotFoundError):
            parse_from_file("nonexistent.md")

    def test_missing_files_all_reported(self):
        """All missing files are reported before exiting."""
        stderr = StringIO()
        with (
            patch("sys.stderr", stderr),
            self.assertRaises(SystemExit),
        ):
            main(["missing_a.md", "missing_b.md"])
        output = stderr.getvalue()
        self.assertIn("missing_a.md", output)
        self.assertIn("missing_b.md", output)

    def test_parse_file(self):
        output = parse_from_file(test_md)
        expected = test_rst.read_text()
        self.assertEqual(output.strip(), expected.strip())

    def test_dryrun(self):
        """--dry-run prints to stdout and does not write a file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            md, rst = self._copy_to_tmp(Path(tmpdir))
            self.assertFalse(rst.exists())
            stdout = StringIO()
            with patch("sys.stdout", stdout):
                main(["--dry-run", str(md)])
            self.assertFalse(rst.exists())
            expected = test_rst.read_text()
            # --dry-run adds a trailing newline via print()
            self.assertEqual(stdout.getvalue().strip(), expected.strip())

    def test_write_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            md, rst = self._copy_to_tmp(Path(tmpdir))
            self.assertFalse(rst.exists())
            main([str(md)])
            self.assertTrue(rst.exists())

    def test_overwrite_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            md, rst = self._copy_to_tmp(Path(tmpdir))
            rst.write_text("test")
            with (
                patch("sys.stdin") as mock_stdin,
                patch("builtins.input", return_value="y"),
            ):
                mock_stdin.isatty.return_value = True
                main([str(md)])
            self.assertTrue(rst.exists())
            first_line = rst.read_text().splitlines()[0]
            self.assertNotIn("test", first_line)

    def test_overwrite_option(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            md, rst = self._copy_to_tmp(Path(tmpdir))
            rst.write_text("test")
            with patch("builtins.input", return_value="y") as m_input:
                main(["--overwrite", str(md)])
            self.assertTrue(rst.exists())
            self.assertFalse(m_input.called)
            first_line = rst.read_text().splitlines()[0]
            self.assertNotIn("test", first_line)

    def test_decline_overwrite(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            md, rst = self._copy_to_tmp(Path(tmpdir))
            rst.write_text("original")
            stderr = StringIO()
            with (
                patch("sys.stdin") as mock_stdin,
                patch("builtins.input", return_value="n"),
                patch("sys.stderr", stderr),
            ):
                mock_stdin.isatty.return_value = True
                main([str(md)])
            self.assertEqual(rst.read_text(), "original")
            self.assertIn("Skipping", stderr.getvalue())

    def test_non_interactive_skip(self):
        """Non-interactive mode skips with a warning to stderr."""
        with tempfile.TemporaryDirectory() as tmpdir:
            md, rst = self._copy_to_tmp(Path(tmpdir))
            rst.write_text("original")
            stderr = StringIO()
            with (
                patch("sys.stdin") as mock_stdin,
                patch("sys.stderr", stderr),
            ):
                mock_stdin.isatty.return_value = False
                main([str(md)])
            self.assertEqual(rst.read_text(), "original")
            self.assertIn("--overwrite", stderr.getvalue())

    def test_underscore_option(self):
        stdout = StringIO()
        with patch("sys.stdout", stdout):
            main(["--no-underscore-emphasis", "--dry-run", str(test_md)])
        output = stdout.getvalue()
        self.assertIn("__content__", output)
        self.assertNotIn("**content**", output)

    def test_anonymous_reference_option(self):
        stdout = StringIO()
        with patch("sys.stdout", stdout):
            main(["--anonymous-references", "--dry-run", str(test_md)])
        self.assertIn("`A link to GitHub <http://github.com/>`__", stdout.getvalue())

    def test_disable_inline_math(self):
        stdout = StringIO()
        with patch("sys.stdout", stdout):
            main(["--disable-inline-math", "--dry-run", str(test_md)])
        output = stdout.getvalue()
        self.assertIn("``$E = mc^2$``", output)
        self.assertNotIn(":math:", output)

    def test_parse_relative_links_option(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            md = Path(tmpdir) / "rel.md"
            md.write_text("See [other page](other.md).\n")
            stdout = StringIO()
            with patch("sys.stdout", stdout):
                main(["--parse-relative-links", "--dry-run", str(md)])
            self.assertIn(":doc:`other page <other>`", stdout.getvalue())

    def test_use_mermaid_option(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            md = Path(tmpdir) / "merm.md"
            md.write_text("""\
```mermaid
graph TD
    A --> B
```
""")
            stdout = StringIO()
            with patch("sys.stdout", stdout):
                main(["--use-mermaid", "--dry-run", str(md)])
            self.assertIn(".. mermaid::", stdout.getvalue())

    def test_version_flag(self):
        p = subprocess.run(
            [sys.executable, "-m", "m2r2", "--version"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(p.returncode, 0)
        self.assertRegex(p.stdout.strip(), r"^m2r2 \d+\.\d+\.\d+")

    def test_multiple_input_files(self):
        """Passing multiple files should convert each one."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            md1 = tmppath / "a.md"
            md2 = tmppath / "b.md"
            md1.write_text("# File A\n")
            md2.write_text("# File B\n")

            main([str(md1), str(md2)])

            rst1 = tmppath / "a.rst"
            rst2 = tmppath / "b.rst"
            self.assertTrue(rst1.exists())
            self.assertTrue(rst2.exists())
            self.assertIn("File A", rst1.read_text())
            self.assertIn("File B", rst2.read_text())

    def test_subprocess_convert(self):
        """Integration test: convert a file via ``python -m m2r2 --dry-run``."""
        p = subprocess.run(
            [sys.executable, "-m", "m2r2", "--dry-run", str(test_md)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(p.returncode, 0, msg=p.stderr)
        expected = test_rst.read_text()
        self.assertEqual(p.stdout.strip(), expected.strip())
