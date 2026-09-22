import os
from typing import ClassVar

from docutils import io, statemachine, utils
from docutils.parsers import rst
from docutils.parsers.rst import directives

from m2r2.sphinx.converter import SphinxM2R2


class MdInclude(rst.Directive):
    """Include a Markdown file in a Sphinx document.

    Read the file and convert its selected content to reStructuredText,
    then insert the result into the parser's input.
    """

    required_arguments = 1
    optional_arguments = 0
    option_spec: ClassVar[dict] = {
        "start-line": int,
        "end-line": int,
        "encoding": directives.encoding,
        "tab-width": int,
    }

    def make_include_path_relative_to_working_directory(self):
        source_path = self.state_machine.get_source(self.lineno - 1)
        source_directory = os.path.dirname(os.path.abspath(source_path))

        include_path = directives.path(self.arguments[0])
        resolved_path = os.path.normpath(os.path.join(source_directory, include_path))

        return utils.relative_path(None, resolved_path)

    def run(self):
        settings = self.state.document.settings
        if not settings.file_insertion_enabled:
            raise self.warning(f'"{self.name}" directive disabled.')

        path = self.make_include_path_relative_to_working_directory()
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

        start_line = self.options.get("start-line")
        end_line = self.options.get("end-line")
        try:
            if start_line is not None or end_line is not None:
                lines = include_file.readlines()
                raw_text = "".join(lines[start_line:end_line])
            else:
                raw_text = include_file.read()
        except UnicodeError as error:
            raise self.severe(
                f'Problem with "{self.name}" directive:\n{io.error_string(error)}'
            ) from error

        converter = SphinxM2R2(self.state.document)
        include_lines = statemachine.string2lines(
            converter(raw_text), tab_width, convert_whitespace=True
        )
        self.state_machine.insert_input(include_lines, path)
        return []
