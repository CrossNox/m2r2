"""Resolve links to Markdown headings the way GitHub names them.

Markdown authors link to a heading with the anchor GitHub gives it, such as
``#bugfixes-1`` for the second "Bugfixes". docutils and Sphinx name sections
differently, so this module records, for every document Sphinx reads, which
section each GitHub anchor stands for, and points those links at that section.
"""

from __future__ import annotations

import os
import unicodedata
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from docutils import nodes, utils
from sphinx import addnodes
from sphinx.util import docname_join, logging
from sphinx.util.nodes import make_refnode, split_explicit_title

from m2r2.rst.renderer import HEADING_ANCHOR_ROLE_NAME

if TYPE_CHECKING:
    from docutils.parsers.rst.states import Inliner
    from sphinx.application import Sphinx
    from sphinx.environment import BuildEnvironment

logger = logging.getLogger(__name__)

#: Unicode categories GitHub keeps in an anchor: letters, marks, numbers, and
#: connector punctuation such as the underscore.
_KEPT_CATEGORY_PREFIXES = ("L", "M", "N")
_KEPT_CATEGORIES = ("Pc",)


def slugify_heading_like_github(title: str) -> str:
    """Turn the text of a heading into the anchor GitHub gives it, before numbering."""
    kept = "".join(
        character
        for character in title.lower()
        if character in (" ", "-")
        or unicodedata.category(character).startswith(_KEPT_CATEGORY_PREFIXES)
        or unicodedata.category(character) in _KEPT_CATEGORIES
    )
    return kept.replace(" ", "-")


def assign_github_heading_slugs(titles: Iterable[str]) -> list[str]:
    """Name each heading of a document the way GitHub does, numbering repeats.

    The second "Bugfixes" becomes ``bugfixes-1``. A number GitHub would give
    that another heading already has as its own anchor is skipped.
    """
    occurrences: dict[str, int] = {}
    slugs = []
    for title in titles:
        original = slugify_heading_like_github(title)
        slug = original
        while slug in occurrences:
            occurrences[original] += 1
            slug = f"{original}-{occurrences[original]}"
        occurrences[slug] = 0
        slugs.append(slug)
    return slugs


def find_heading_anchors(env: BuildEnvironment) -> dict[str, dict[str, str]]:
    """Return the map from each document to its GitHub anchors and section ids."""
    if not hasattr(env, "m2r2_heading_anchors"):
        env.m2r2_heading_anchors = {}
    return env.m2r2_heading_anchors


def record_heading_anchors(app: Sphinx, doctree: nodes.document) -> None:
    """Record which section of the document just read each GitHub anchor names."""
    sections = list(doctree.findall(nodes.section))
    titles = [section[0].astext() for section in sections]
    slugs = assign_github_heading_slugs(titles)
    find_heading_anchors(app.env)[app.env.docname] = {
        slug: section["ids"][0] for slug, section in zip(slugs, sections)
    }


def forget_heading_anchors(app: Sphinx, env: BuildEnvironment, docname: str) -> None:
    """Drop the anchors of a document Sphinx is about to read again."""
    find_heading_anchors(env).pop(docname, None)


def merge_heading_anchors(
    app: Sphinx,
    env: BuildEnvironment,
    docnames: Iterable[str],
    other: BuildEnvironment,
) -> None:
    """Take the anchors a worker process of a parallel build recorded."""
    anchors = find_heading_anchors(env)
    other_anchors = find_heading_anchors(other)
    for docname in docnames:
        anchors[docname] = other_anchors[docname]


def create_heading_anchor_reference(
    name: str,
    rawtext: str,
    text: str,
    lineno: int,
    inliner: Inliner,
    options: dict[str, Any] | None = None,
    content: list[str] | None = None,
) -> tuple[list[nodes.Node], list[nodes.system_message]]:
    """Create the reference that a link to a heading's GitHub anchor resolves from."""
    has_title, title, target = split_explicit_title(utils.unescape(text))
    reference = addnodes.pending_xref(
        rawtext,
        refdomain="",
        reftype=HEADING_ANCHOR_ROLE_NAME,
        reftarget=target,
        refexplicit=has_title,
        refdoc=inliner.document.settings.env.docname,
    )
    reference += nodes.inline(title, title)
    return [reference], []


def resolve_heading_anchor_reference(
    app: Sphinx,
    env: BuildEnvironment,
    node: addnodes.pending_xref,
    contnode: nodes.Element,
) -> nodes.Element | None:
    """Point a link at the section whose GitHub anchor it names.

    A link naming a document or an anchor the project lacks gets a warning and
    renders as its text alone.
    """
    if node["reftype"] != HEADING_ANCHOR_ROLE_NAME:
        return None

    path, _, slug = node["reftarget"].partition("#")
    source_docname = node["refdoc"]
    if path == "":
        target_docname = source_docname
    else:
        target_docname = docname_join(source_docname, os.path.splitext(path)[0])

    if target_docname not in env.found_docs:
        logger.warning(
            "m2r2 found no document %r for the link to %r",
            target_docname,
            node["reftarget"],
            location=node,
            type="m2r2",
            subtype="anchor",
        )
        return contnode

    section_id = find_heading_anchors(env)[target_docname].get(slug)
    if section_id is None:
        logger.warning(
            "m2r2 found no heading with the anchor #%s in %r",
            slug,
            target_docname,
            location=node,
            type="m2r2",
            subtype="anchor",
        )
        return contnode

    return make_refnode(
        app.builder, source_docname, target_docname, section_id, contnode
    )


def register_heading_anchors(app: Sphinx) -> None:
    """Register the role for heading links and the handlers that resolve them."""
    app.add_role(HEADING_ANCHOR_ROLE_NAME, create_heading_anchor_reference)
    app.connect("doctree-read", record_heading_anchors)
    app.connect("env-purge-doc", forget_heading_anchors)
    app.connect("env-merge-info", merge_heading_anchors)
    app.connect("missing-reference", resolve_heading_anchor_reference)
