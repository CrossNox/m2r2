# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

M2R2 is a Python package that converts Markdown files to reStructuredText (rst) format, with support for Sphinx integration. It's a fork of the original m2r package, built on top of the mistune markdown parser (v3.0+).

## Development Commands

### Package Management (uv)
- Install dependencies: `uv sync`
- Add a dependency: `uv add <package>`
- Add a dev dependency: `uv add --group dev <package>`
- Build package: `uv build`

### Testing
- Run tests: `uv run pytest`
- Run tests with coverage: `uv run pytest --cov=m2r2`
- Run specific test: `uv run pytest tests/test_cli.py::TestConvert::test_parse_file`
- Run tests with specific Python: `uv run --python 3.11 pytest`

### Code Quality
- Format code: `uv run ruff format m2r2/`
- Lint code: `uv run ruff check m2r2/`
- Lint and fix: `uv run ruff check --fix m2r2/`
- Type checking: `uv run mypy m2r2/`
- Security scan: `uv run bandit -r m2r2/`

### Documentation
- Build docs: `uv run sphinx-build -E -W -n -j auto -b html docs docs/_build/html`

## Architecture

### Package Structure

```
m2r2/
├── __init__.py          # Exports M2R2, convert, parse_from_file, setup
├── __main__.py          # Entry point for `python -m m2r2`
├── m2r2.py              # Core M2R2 converter class
├── parser.py            # Sphinx M2R2Parser integration
├── cli/                 # CLI module
│   ├── __init__.py
│   └── m2r2.py          # CLI implementation
├── rst/                 # RST rendering components
│   ├── __init__.py
│   ├── renderer.py      # Custom RST renderer
│   └── plugins.py       # Mistune plugins for RST
└── sphinx/              # Sphinx extension
    ├── __init__.py
    ├── m2r2.py          # Sphinx setup() function
    └── directives.py    # Sphinx directives (mdinclude)
```

### Core Components

**M2R2 Class** (`m2r2/m2r2.py`): Main converter class that orchestrates Markdown to reStructuredText conversion using mistune parser with custom RST renderer.

**RestRenderer** (`m2r2/rst/renderer.py`): Custom RST renderer extending mistune's RSTRenderer, handles RST-specific formatting like heading marks, list indentation, and inline directives.

**Visual List Parser** (`m2r2/rst/plugins.py`): Custom list parser that handles lenient 2-space indentation for nested lists (backward compatible with original m2r).

**Sphinx Extension** (`m2r2/sphinx/m2r2.py`): Sphinx integration with `setup()` function and `mdinclude` directive.

### Installation Options

```bash
# Core (markdown to rst conversion)
uv add m2r2

# With Sphinx support
uv add m2r2[sphinx]
```

### Key Features

- **RST Directive Support**: Inline and block-level RST directives within Markdown
- **Sphinx Integration**: Full Sphinx extension with `mdinclude` directive
- **Configurable Options**:
  - `no_underscore_emphasis`: Disable underscore-based emphasis
  - `parse_relative_links`: Convert relative links to RST references
  - `anonymous_references`: Use anonymous RST references
  - `disable_inline_math`: Disable inline math parsing
  - `use_mermaid`: Enable mermaid diagram support

### Testing

Tests are in `tests/` directory:
- `test_cli.py`: CLI functionality tests
- `test_renderer.py`: Renderer component tests
- `test_sphinx.py`: Sphinx integration tests (setup, parser, mdinclude)
- Test files: `test.md`, `test.rst` for conversion validation

## Dependencies

- **mistune**: Markdown parser (v3.0+)
- **docutils**: RST processing (v0.19+)
- **sphinx**: Documentation system (optional, for extension features)

## Development Notes

- Uses uv for dependency management and packaging
- Supports Python 3.9+
- Uses ruff for linting and formatting
- Pre-commit hooks enforce code quality standards

## Best Practices
- Always use `uv run` for commands, never bare `python`
