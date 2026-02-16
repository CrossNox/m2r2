from m2r2 import __version__
from m2r2.m2r2 import M2R2_CONFIG
from m2r2.parser import M2R2Parser
from m2r2.sphinx.directives import MdInclude


def setup(app):
    """Register m2r2 config values, source parser, and mdinclude directive."""
    for conf_name, _, default in M2R2_CONFIG:
        if conf_name == "m2r_use_mermaid":
            default = "sphinxcontrib.mermaid" in app.config.extensions
        app.add_config_value(conf_name, default, "env")
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
