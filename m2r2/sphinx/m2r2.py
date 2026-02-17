import warnings

from m2r2.m2r2 import __version__
from m2r2.parser import M2R2Parser
from m2r2.sphinx.directives import MdInclude


def _migrate_deprecated_config(app, config):
    """Copy deprecated ``no_underscore_emphasis`` to ``m2r_no_underscore_emphasis``."""
    if config.no_underscore_emphasis:
        warnings.warn(
            "The 'no_underscore_emphasis' config value is deprecated. "
            "Use 'm2r_no_underscore_emphasis' instead.",
            DeprecationWarning,
            stacklevel=1,
        )
        config.m2r_no_underscore_emphasis = config.no_underscore_emphasis


def setup(app):
    """Register m2r2 config values, source parser, and mdinclude directive."""
    # Deprecated name kept for backward compatibility
    app.add_config_value("no_underscore_emphasis", False, "env")
    app.add_config_value("m2r_no_underscore_emphasis", False, "env")
    app.add_config_value("m2r_parse_relative_links", False, "env")
    app.add_config_value("m2r_anonymous_references", False, "env")
    app.add_config_value("m2r_disable_inline_math", False, "env")
    app.add_config_value(
        "m2r_use_mermaid",
        "sphinxcontrib.mermaid" in app.config.extensions,
        "env",
    )
    try:
        app.connect("config-inited", _migrate_deprecated_config)
    except KeyError:
        # Sphinx < 1.8 doesn't have the config-inited event
        pass
    try:
        app.add_source_suffix(".md", "markdown")
        app.add_source_parser(M2R2Parser)
    except (TypeError, AttributeError):
        app.add_source_parser(".md", M2R2Parser)  # Sphinx < 4.0
    app.add_directive("mdinclude", MdInclude)
    return {
        "version": __version__,
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
