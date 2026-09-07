import os
from typing import ClassVar

from docutils import io, statemachine, utils
from docutils.parsers import rst
from docutils.parsers.rst import directives

from m2r2.m2r2 import M2R2
from m2r2.rst.renderer import RestRenderer


class MdInclude(rst.Directive):
    """Directive class to include markdown in sphinx.

    Load a file and convert it to rst and insert as a node.
    """

    required_arguments = 1
    optional_arguments = 0
    option_spec: ClassVar[dict] = {
        "start-line": int,
        "end-line": int,
        "encoding": directives.encoding,
        "tab-width": int,
    }

    def run(self):
        if not self.state.document.settings.file_insertion_enabled:
            raise self.warning(f'"{self.name}" directive disabled.')
        source = self.state_machine.get_source(self.lineno - 1)
        source_dir = os.path.dirname(os.path.abspath(source))
        path = rst.directives.path(self.arguments[0])
        path = os.path.normpath(os.path.join(source_dir, path))
        path = utils.relative_path(None, path)

        # get options
        encoding = self.options.get(
            "encoding", self.state.document.settings.input_encoding
        )
        e_handler = self.state.document.settings.input_encoding_error_handler
        tab_width = self.options.get(
            "tab-width", self.state.document.settings.tab_width
        )

        # open the including file
        try:
            self.state.document.settings.record_dependencies.add(path)
            include_file = io.FileInput(
                source_path=path, encoding=encoding, error_handler=e_handler
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

        # read from the file
        startline = self.options.get("start-line", None)
        endline = self.options.get("end-line", None)
        try:
            if startline is not None or endline is not None:
                lines = include_file.readlines()
                rawtext = "".join(lines[startline:endline])
            else:
                rawtext = include_file.read()
        except UnicodeError as error:
            raise self.severe(
                f'Problem with "{self.name}" directive:\n{io.error_string(error)}'
            ) from error

        config = self.state.document.settings.env.config
        converter = M2R2(
            no_underscore_emphasis=config.m2r_no_underscore_emphasis,
            disable_inline_math=config.m2r_disable_inline_math,
            renderer=RestRenderer(
                parse_relative_links=config.m2r_parse_relative_links,
                anonymous_references=config.m2r_anonymous_references,
                use_mermaid=config.m2r_use_mermaid,
                is_sphinx=True,
                existing_substitutions=self.state.document.substitution_defs,
            ),
        )
        include_lines = statemachine.string2lines(
            converter(rawtext), tab_width, convert_whitespace=True
        )
        self.state_machine.insert_input(include_lines, path)
        return []
