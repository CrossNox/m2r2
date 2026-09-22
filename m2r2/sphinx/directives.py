import os
from typing import Any, ClassVar, cast

from docutils import io, statemachine, utils
from docutils.parsers import rst
from docutils.parsers.rst import directives
from docutils.parsers.rst.directives.misc import Include

from m2r2.sphinx.converter import SphinxM2R2

# docutils' include always declares its options, though the stubs allow None.
_DOCUTILS_INCLUDE_OPTIONS = cast("dict[str, Any]", Include.option_spec)


class MdInclude(rst.Directive):
    """Include a Markdown file in a Sphinx document.

    The directive is docutils' include, except that the file is Markdown and
    converts to reStructuredText before docutils parses it. With ``literal`` or
    ``code``, the file is shown instead of parsed, so nothing converts.
    """

    required_arguments = 1
    optional_arguments = 0
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

        A relative path is relative to the file holding the directive. An
        absolute one starts at the Sphinx source directory, as it does for
        Sphinx's own include.
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
        """Keep the lines that start-line and end-line, or lines, select."""
        lines = text.splitlines(keepends=True)
        start_line = self.options.get("start-line")
        end_line = self.options.get("end-line")

        if "lines" not in self.options:
            if start_line is None and end_line is None:
                return text
            return "".join(lines[start_line:end_line])

        if start_line is not None or end_line is not None:
            raise self.severe(
                f'Problem with "lines" option of "{self.name}" directive:\n'
                'It cannot be combined with "start-line" or "end-line".'
            )
        line_indexes = self.parse_line_selection(self.options["lines"], len(lines))
        return "".join(lines[index] for index in line_indexes)

    def parse_line_selection(self, selection, line_count):
        """Turn a selection such as "1, 3-4, 7-" into the indexes of the lines it names.

        Each entry is a line number, a range, a range from the first line such
        as "-4", or a range to the last line such as "7-". Lines come out in the
        order the entries name them.
        """
        indexes: list[int] = []
        for entry in selection.split(","):
            first_text, dash, last_text = entry.strip().partition("-")
            try:
                if dash == "":
                    first = last = int(first_text)
                elif first_text == "" and last_text == "":
                    raise ValueError(entry)
                else:
                    first = 1 if first_text == "" else int(first_text)
                    last = line_count if last_text == "" else int(last_text)
            except ValueError as error:
                raise self.severe(
                    f'Problem with "lines" option of "{self.name}" directive:\n'
                    f"Cannot read {entry.strip()!r} as a line or a range of lines."
                ) from error

            if first < 1 or last > line_count or first > line_count:
                raise self.severe(
                    f'Problem with "lines" option of "{self.name}" directive:\n'
                    f"{entry.strip()!r} is outside the file, which has "
                    f"{line_count} lines."
                )
            if first > last:
                raise self.severe(
                    f'Problem with "lines" option of "{self.name}" directive:\n'
                    f"The range {entry.strip()!r} ends before it starts."
                )

            indexes.extend(range(first - 1, last))

        return indexes

    def clip_text_between_markers(self, text):
        """Keep the text after the start-after marker and before the end-before one.

        Each marker goes with everything on its far side, as docutils' include
        does. A marker the text lacks is a severe error.
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

    def show_file_without_converting(self, included_file):
        """Show the Markdown file as a literal or code block, through docutils' include."""
        include = Include(
            self.name,
            [included_file],
            self.options,
            self.content,
            self.lineno,
            self.content_offset,
            self.block_text,
            self.state,
            self.state_machine,
        )
        return include.run()

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
            return self.show_file_without_converting(included_file)

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

        converter = SphinxM2R2(self.state.document)
        include_lines = statemachine.string2lines(
            converter(raw_text), tab_width, convert_whitespace=True
        )
        self.state_machine.insert_input(include_lines, path)
        return []
