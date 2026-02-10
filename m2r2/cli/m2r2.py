import argparse
from pathlib import Path

from m2r2 import convert


class Options:
    """Global options object for backward compatibility with tests."""

    def __init__(self):
        self.overwrite = False
        self.dry_run = False
        self.no_underscore_emphasis = False
        self.parse_relative_links = False
        self.anonymous_references = False
        self.disable_inline_math = False
        self.input_files = []


# Global options object for backward compatibility
options = Options()


def parse_arguments() -> argparse.Namespace | None:
    global options
    parser = argparse.ArgumentParser(description="Convert files to reST format")
    # TODO: add breaking change to changelog
    parser.add_argument(
        "input_files", nargs="*", type=Path, help="Files to convert to reST format"
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        default=False,
        help="Overwrite output file without confirmation",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Print conversion result without saving output file",
    )
    parser.add_argument(
        "--no-underscore-emphasis",
        action="store_true",
        default=False,
        help="Do not use underscore (_) for emphasis",
    )
    parser.add_argument(
        "--parse-relative-links",
        action="store_true",
        default=False,
        help="Parse relative links into ref or doc directives",
    )
    parser.add_argument(
        "--anonymous-references",
        action="store_true",
        default=False,
        help="Use anonymous references in generated rst",
    )
    parser.add_argument(
        "--disable-inline-math",
        action="store_true",
        default=False,
        help="Disable parsing inline math",
    )

    args = parser.parse_args()

    # Update global options for backward compatibility
    options.overwrite = args.overwrite
    options.dry_run = args.dry_run
    options.no_underscore_emphasis = args.no_underscore_emphasis
    options.parse_relative_links = args.parse_relative_links
    options.anonymous_references = args.anonymous_references
    options.disable_inline_math = args.disable_inline_math
    options.input_files = args.input_files

    if not args.input_files:
        parser.print_help()
        return None

    return args


def parse_from_file(file: str | Path, encoding: str = "utf-8", **kwargs) -> str:
    file_path = Path(file)
    if not file_path.exists():
        raise FileNotFoundError(f"No such file exists: {file_path}")

    with open(file_path, encoding=encoding) as f:
        src = f.read()

    return convert(src, **kwargs)


def save_to_file(
    file: str | Path, content: str, encoding: str = "utf-8", overwrite: bool = False
) -> None:
    """
    Save content to a file, optionally overwriting existing files.

    Args:
        file (str): The input file path.
        content (str): The content to be written to the file.
        encoding (str, optional): The encoding to use for the file. Defaults to "utf-8".
        overwrite (bool, optional): Whether to overwrite existing files without prompting. Defaults to False.

    Returns:
        None
    """
    target = Path(file).with_suffix(".rst")

    if not overwrite and target.exists():
        confirm = input(f"{target} already exists. Overwrite it? [y/N]: ").lower()
        if confirm not in ("y", "yes"):
            print(f"Skipping {file}")
            return

    with open(target, "w", encoding=encoding) as f:
        f.write(content)


def main():
    args = parse_arguments()

    if args is None:
        return

    for file in args.input_files:
        output = parse_from_file(
            file,
            no_underscore_emphasis=args.no_underscore_emphasis,
            parse_relative_links=args.parse_relative_links,
            anonymous_references=args.anonymous_references,
            disable_inline_math=args.disable_inline_math,
        )
        if args.dry_run:
            print(output)
        else:
            save_to_file(file, output, overwrite=args.overwrite)


if __name__ == "__main__":
    main()
