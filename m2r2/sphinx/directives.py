import os
from typing import Any, ClassVar, cast

from docutils import io, statemachine, utils
from docutils.parsers.rst import directives
from docutils.parsers.rst.directives.misc import Include

from m2r2.sphinx.converter import SphinxM2R2

# docutils' include always declares its options, though the stubs allow None.
_DOCUTILS_INCLUDE_OPTIONS = cast("dict[str, Any]", Include.option_spec)


class MdInclude(Include):
    """Include a Markdown file in a Sphinx document.

    Use ``literal`` or ``code`` to display the source without conversion.
    """

    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = False
    # Every option of docutils' include but "parser", since the parser is what
    # this directive chooses. The options that show the file take docutils'
    # own converters, so they read the same as in the version installed.
    option_spec: ClassVar[dict] = {
        "start-line": int,
        "end-line": int,
        # Borrowed from Sphinx's literalinclude, which selects lines this way.
        "lines": directives.unchanged_required,
        "start-after": directives.unchanged_required,
        "end-before": directives.unchanged_required,
        "encoding": directives.encoding,
        "tab-width": int,
        "literal": _DOCUTILS_INCLUDE_OPTIONS["literal"],
        "code": _DOCUTILS_INCLUDE_OPTIONS["code"],
        "number-lines": _DOCUTILS_INCLUDE_OPTIONS["number-lines"],
        "name": _DOCUTILS_INCLUDE_OPTIONS["name"],
        "class": _DOCUTILS_INCLUDE_OPTIONS["class"],
    }

    def find_included_file(self):
        """Return the absolute path of the file to include.

        Resolve relative paths from the file containing the directive.
        Resolve paths starting with ``/`` from the Sphinx source directory.
        """
        include_path = directives.path(self.arguments[0])
        if include_path.startswith("/"):
            source_directory = str(self.state.document.settings.env.srcdir)
            include_path = include_path.lstrip("/")
        else:
            source_path = self.state_machine.get_source(self.lineno - 1)
            source_directory = os.path.dirname(os.path.abspath(source_path))

        return os.path.normpath(os.path.join(source_directory, include_path))

    def select_lines(self, text):
        """Select source lines using the directive's line options."""
        source_lines = text.splitlines(keepends=True)
        start_line = self.options.get("start-line")
        end_line = self.options.get("end-line")

        if "lines" not in self.options:
            if start_line is None and end_line is None:
                return text
            return "".join(source_lines[start_line:end_line])

        if start_line is not None or end_line is not None:
            raise self.severe(
                f'Problem with "lines" option of "{self.name}" directive:\n'
                'It cannot be combined with "start-line" or "end-line".'
            )
        selected_line_indexes = self.parse_line_selection(
            self.options["lines"], len(source_lines)
        )
        return "".join(source_lines[line_index] for line_index in selected_line_indexes)

    def parse_line_selection(self, selection, line_count):
        """Convert a line selection to zero-based indexes in selection order.

        Accept one-based line numbers and inclusive ranges, such as ``1, 3-4``.
        Open ranges extend to the first or last line, as in ``-4`` and ``7-``.
        """
        selected_line_indexes: list[int] = []
        for selection_entry in selection.split(","):
            first_line_text, range_separator, last_line_text = (
                selection_entry.strip().partition("-")
            )
            try:
                if range_separator == "":
                    first_line_number = last_line_number = int(first_line_text)
                elif first_line_text == "" and last_line_text == "":
                    raise ValueError(selection_entry)
                else:
                    first_line_number = (
                        1 if first_line_text == "" else int(first_line_text)
                    )
                    last_line_number = (
                        line_count if last_line_text == "" else int(last_line_text)
                    )
            except ValueError as error:
                raise self.severe(
                    f'Problem with "lines" option of "{self.name}" directive:\n'
                    f"Cannot read {selection_entry.strip()!r} as a line or a range of lines."
                ) from error

            if (
                first_line_number < 1
                or last_line_number > line_count
                or first_line_number > line_count
            ):
                raise self.severe(
                    f'Problem with "lines" option of "{self.name}" directive:\n'
                    f"{selection_entry.strip()!r} is outside the file, which has "
                    f"{line_count} lines."
                )
            if first_line_number > last_line_number:
                raise self.severe(
                    f'Problem with "lines" option of "{self.name}" directive:\n'
                    f"The range {selection_entry.strip()!r} ends before it starts."
                )

            selected_line_indexes.extend(range(first_line_number - 1, last_line_number))

        return selected_line_indexes

    def clip_text_between_markers(self, text):
        """Select text using the directive's start and end markers.

        Exclude the markers. Raise a severe directive error if a specified
        marker is missing.
        """
        start_marker = self.options.get("start-after")
        if start_marker is not None:
            start_index = text.find(start_marker)
            if start_index < 0:
                raise self.severe(
                    f'Problem with "start-after" option of "{self.name}" '
                    "directive:\nText not found."
                )
            text = text[start_index + len(start_marker) :]

        end_marker = self.options.get("end-before")
        if end_marker is not None:
            end_index = text.find(end_marker)
            if end_index < 0:
                raise self.severe(
                    f'Problem with "end-before" option of "{self.name}" '
                    "directive:\nText not found."
                )
            text = text[:end_index]

        return text

    def run(self):
        settings = self.state.document.settings
        if not settings.file_insertion_enabled:
            raise self.warning(f'"{self.name}" directive disabled.')

        included_file = self.find_included_file()
        # Sphinx counts a noted file as included, so a Markdown source it
        # would also build on its own is not reported as missing from a toctree.
        settings.env.note_included(included_file)

        if "literal" in self.options or "code" in self.options:
            if "lines" in self.options:
                # docutils' include, which shows the file, knows no such option.
                raise self.severe(
                    f'Problem with "lines" option of "{self.name}" directive:\n'
                    'It cannot be combined with "literal" or "code".'
                )
            self.arguments = [included_file]
            return super().run()

        path = utils.relative_path(None, included_file)
        encoding = self.options.get("encoding", settings.input_encoding)
        encoding_error_handler = settings.input_encoding_error_handler
        tab_width = self.options.get("tab-width", settings.tab_width)

        try:
            settings.record_dependencies.add(path)
            include_file = io.FileInput(
                source_path=path,
                encoding=encoding,
                error_handler=encoding_error_handler,
            )
        except UnicodeEncodeError as error:
            raise self.severe(
                f'Problems with "{self.name}" directive path:\n'
                f'Cannot encode input file path "{path}" '
                "(wrong locale?)."
            ) from error
        except OSError as error:
            raise self.severe(
                f'Problems with "{self.name}" directive path:\n{io.error_string(error)}.'
            ) from error

        try:
            raw_text = include_file.read()
        except UnicodeError as error:
            raise self.severe(
                f'Problem with "{self.name}" directive:\n{io.error_string(error)}'
            ) from error

        raw_text = self.select_lines(raw_text)
        raw_text = self.clip_text_between_markers(raw_text)

        converter = SphinxM2R2(self.state.document, source_path=included_file)
        include_lines = statemachine.string2lines(
            converter(raw_text), tab_width, convert_whitespace=True
        )
        self.state_machine.insert_input(include_lines, path)
        return []
