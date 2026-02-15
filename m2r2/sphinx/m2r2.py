from m2r2 import __version__
from m2r2.parser import M2R2Parser
from m2r2.sphinx.directives import MdInclude

# Mapping of Sphinx conf.py config names to M2R2 constructor kwargs.
# Each entry: (sphinx_config_name, m2r2_kwarg, default_value)
M2R2_CONFIG = (
    ("no_underscore_emphasis", "no_underscore_emphasis", False),
    ("m2r_parse_relative_links", "parse_relative_links", False),
    ("m2r_anonymous_references", "anonymous_references", False),
    ("m2r_disable_inline_math", "disable_inline_math", False),
    ("m2r_use_mermaid", "use_mermaid", None),  # default computed at setup time
)


def setup(app):
    """When used for sphinx extension."""
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
