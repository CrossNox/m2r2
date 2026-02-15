from m2r2 import __version__
from m2r2.parser import M2R2Parser
from m2r2.sphinx.directives import MdInclude


def setup(app):
    """When used for sphinx extension."""
    app.add_config_value("no_underscore_emphasis", False, "env")
    app.add_config_value("m2r_parse_relative_links", False, "env")
    app.add_config_value("m2r_anonymous_references", False, "env")
    app.add_config_value("m2r_disable_inline_math", False, "env")
    app.add_config_value(
        "m2r_use_mermaid", "sphinxcontrib.mermaid" in app.config.extensions, "env"
    )
    try:
        app.add_source_parser(".md", M2R2Parser)  # for older sphinx versions
    except (TypeError, AttributeError):
        app.add_source_suffix(".md", "markdown")
        app.add_source_parser(M2R2Parser)
    app.add_directive("mdinclude", MdInclude)
    metadata = {
        "version": __version__,
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
    return metadata
