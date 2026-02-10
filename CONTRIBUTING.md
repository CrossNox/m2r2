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

### Code Quality

```bash
# Format code
uv run ruff format m2r2/ tests/

# Lint code
uv run ruff check m2r2/ tests/

# Lint and auto-fix
uv run ruff check --fix m2r2/ tests/

# Type checking
uv run mypy m2r2/

# Security scan
uv run bandit -r m2r2/
```

### Building Documentation

```bash
uv run sphinx-build -E -W -n -j auto -b html docs docs/_build/html
```

## Project Structure

```
m2r2/
├── __init__.py          # Exports M2R2, convert
├── __main__.py          # Entry point for `python -m m2r2`
├── m2r2.py              # Core M2R2 converter class
├── parser.py            # Sphinx M2R2Parser integration
├── cli/                 # CLI module
│   └── m2r2.py          # CLI implementation
├── rst/                 # RST rendering components
│   ├── renderer.py      # Custom RST renderer
│   ├── plugins.py       # Mistune plugins for RST
│   └── directives.py    # Sphinx directives (mdinclude)
└── sphinx/              # Sphinx extension
    └── m2r2.py          # Sphinx setup() function
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

3. Format and lint your code:
   ```bash
   uv run ruff format m2r2/ tests/
   uv run ruff check --fix m2r2/ tests/
   ```

4. Commit your changes with a clear message:
   ```bash
   git commit -m "Add feature: description of your changes"
   ```

5. Push and create a pull request.

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
