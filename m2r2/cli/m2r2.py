"""M2R2 command-line interface."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from m2r2.m2r2 import __version__, convert

if TYPE_CHECKING:
    from collections.abc import Sequence


def parse_from_file(
    file: str | Path,
    encoding: str = "utf-8",
    *,
    no_underscore_emphasis: bool = False,
    disable_inline_math: bool = False,
    parse_relative_links: bool = False,
    anonymous_references: bool = False,
    use_mermaid: bool = False,
) -> str:
    """Read a Markdown file and convert it to reStructuredText.

    Args:
        file: Path to the Markdown file.
        encoding: File encoding. Defaults to "utf-8".
        no_underscore_emphasis: Disable underscore-based emphasis.
        disable_inline_math: Disable inline math parsing.
        parse_relative_links: Convert relative links to RST references.
        anonymous_references: Use anonymous RST references.
        use_mermaid: Render mermaid code blocks as directives.

    Returns:
        The converted reStructuredText content.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    path = Path(file)
    if not path.exists():
        raise FileNotFoundError(f"No such file exists: {path}")

    return convert(
        path.read_text(encoding=encoding),
        no_underscore_emphasis=no_underscore_emphasis,
        disable_inline_math=disable_inline_math,
        parse_relative_links=parse_relative_links,
        anonymous_references=anonymous_references,
        use_mermaid=use_mermaid,
    )


def save_to_file(
    file: str | Path,
    content: str,
    encoding: str = "utf-8",
    overwrite: bool = False,
) -> bool:
    """Save converted content to a .rst file.

    Args:
        file: The input file path (extension will be changed to .rst).
        content: The content to write.
        encoding: File encoding. Defaults to "utf-8".
        overwrite: Skip confirmation prompt. Defaults to False.

    Returns:
        True if file was written, False if skipped.
    """
    target = Path(file).with_suffix(".rst")

    if not overwrite and target.exists():
        if not sys.stdin.isatty():
            print(
                f"Skipping {file} (use --overwrite in non-interactive mode)",
                file=sys.stderr,
            )
            return False
        confirm = input(f"{target} already exists. Overwrite it? [y/N]: ").lower()
        if confirm not in ("y", "yes"):
            print(f"Skipping {file}", file=sys.stderr)
            return False

    target.write_text(content, encoding=encoding)
    return True


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="m2r2",
        description="Convert Markdown to reStructuredText.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "input_files",
        nargs="+",
        type=Path,
        metavar="FILE",
        help="Markdown files to convert",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="overwrite output files without confirmation",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print output to stdout instead of writing files",
    )
    parser.add_argument(
        "--no-underscore-emphasis",
        action="store_true",
        help="disable underscore emphasis (keep _text_ as-is)",
    )
    parser.add_argument(
        "--parse-relative-links",
        action="store_true",
        help="convert relative links to :doc: or :ref: directives",
    )
    parser.add_argument(
        "--anonymous-references",
        action="store_true",
        help="use anonymous references (__ instead of _)",
    )
    parser.add_argument(
        "--disable-inline-math",
        action="store_true",
        help="disable inline math conversion",
    )
    parser.add_argument(
        "--use-mermaid",
        action="store_true",
        help="render mermaid code blocks as .. mermaid:: directives",
    )
    return parser


def run_m2r2(args: argparse.Namespace) -> None:
    """Execute the conversion based on parsed arguments.

    Args:
        args: Parsed command-line arguments.
    """
    # Validate all input files exist before processing any
    missing = [f for f in args.input_files if not f.exists()]
    if len(missing) > 0:
        for f in missing:
            print(f"Error: No such file exists: {f}", file=sys.stderr)
        sys.exit(1)

    for file in args.input_files:
        output = parse_from_file(
            file,
            no_underscore_emphasis=args.no_underscore_emphasis,
            parse_relative_links=args.parse_relative_links,
            anonymous_references=args.anonymous_references,
            disable_inline_math=args.disable_inline_math,
            use_mermaid=args.use_mermaid,
        )
        if args.dry_run:
            print(output)
        else:
            save_to_file(file, output, overwrite=args.overwrite)


def main(argv: Sequence[str] | None = None) -> None:
    """Main entry point for the CLI.

    Args:
        argv: Command-line arguments. Defaults to sys.argv[1:].
    """
    parser = create_parser()
    args = parser.parse_args(argv)
    run_m2r2(args)


if __name__ == "__main__":
    main()
