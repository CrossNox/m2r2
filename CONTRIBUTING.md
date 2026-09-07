# Contributing to M2R2

Thank you for your interest in contributing to M2R2!

## Development Setup

### Prerequisites

- Python 3.9 or higher
- [uv](https://docs.astral.sh/uv/) - Fast Python package manager

### Getting Started

1. Clone the repository:
   ```bash
   git clone https://github.com/crossnox/m2r2.git
   cd m2r2
   ```

2. Install dependencies:
   ```bash
   uv sync
   ```

   This installs all dependencies including dev and test groups.

3. Install pre-commit hooks:
   ```bash
   uv run pre-commit install
   uv run pre-commit install -t pre-push
   ```

## Development Commands

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=m2r2

# Run specific test
uv run pytest tests/test_cli.py::TestConvert::test_parse_file

# Run with a specific Python version
uv run --python 3.11 pytest
```

Conversion tests should check that docutils accepts the generated RST and that
the document keeps its content and structure. Compare document trees when
spacing is incidental. Check literal code content exactly.

### Code Quality

Pre-commit hooks handle formatting, linting, type checking, and tests
automatically. Install them with:

```bash
uv run pre-commit install
uv run pre-commit install -t pre-push
```

To run the commit hooks manually:

```bash
uv run pre-commit run --all-files
```

Run `uv run pytest` separately, or use
`uv run pre-commit run --all-files --hook-stage pre-push` for the test hook.

### Building Documentation

```bash
uv run sphinx-build -E -W -n -j auto -b html docs docs/_build/html
```

### Release Checks

Before a release, build and validate both distributions:

```bash
uv build
uvx twine check dist/*
```

Publishing waits for the Python test matrix, minimum dependency tests, Sphinx
builds, and lint workflow.

## Project Structure

```
m2r2/
├── __init__.py          # Exports M2R2, convert, parse_from_file, __version__, setup
├── m2r2.py              # Core M2R2 converter class
├── parser.py            # M2R2Parser (docutils RST parser subclass)
├── cli/                 # CLI module
│   ├── __init__.py
│   └── m2r2.py          # CLI implementation (parse_from_file, main)
├── rst/                 # RST rendering components
│   ├── renderer.py      # Custom RST renderer (RestRenderer)
│   └── plugins.py       # Mistune plugins (directives, inline math, lists)
└── sphinx/              # Sphinx extension
    ├── m2r2.py          # Sphinx setup() function, config mapping
    └── directives.py    # MdInclude directive
```

## Making Changes

1. Create a new branch for your changes:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes and ensure tests pass:
   ```bash
   uv run pytest
   ```

3. Commit your changes with a clear message:
   ```bash
   git commit -m "Add feature: description of your changes"
   ```

4. Push and create a pull request.

## Code Style

- We use [ruff](https://docs.astral.sh/ruff/) for linting and formatting
- Line length is 88 characters
- Use type hints where practical
- Write docstrings for public functions and classes

## Reporting Issues

If you find a bug or have a feature request, please open an issue at:
https://github.com/crossnox/m2r2/issues

Include:
- Python version
- m2r2 version
- Minimal example to reproduce the issue
- Expected vs actual behavior
