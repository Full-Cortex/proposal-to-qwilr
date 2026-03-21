"""Render proposal data structures into styled HTML for Qwilr text blocks."""
from __future__ import annotations

import html
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from proposal_qwilr.schemas import ScopeItem, TimelinePhase

# Maximum character length for a single token substitution value
MAX_TOKEN_SIZE = 50_000


def _esc(value: str) -> str:
    """Escape user-provided text for safe HTML embedding."""
    return html.escape(value, quote=True)


def render_scope_html(scope: list[ScopeItem]) -> str:
    """Render scope/deliverables as a styled HTML table."""
    rows = ""
    for item in scope:
        rows += (
            f"<tr>"
            f"<td style='padding:12px 16px;border-bottom:1px solid #e5e7eb;font-weight:600;'>"
            f"{_esc(item.deliverable)}</td>"
            f"<td style='padding:12px 16px;border-bottom:1px solid #e5e7eb;'>"
            f"{_esc(item.description)}</td>"
            f"</tr>"
        )
    result = (
        f"<h2>Scope &amp; Deliverables</h2>"
        f"<table style='width:100%;border-collapse:collapse;margin:16px 0;'>"
        f"<thead><tr>"
        f"<th style='padding:12px 16px;text-align:left;border-bottom:2px solid #1a1a2e;"
        f"font-weight:700;'>Deliverable</th>"
        f"<th style='padding:12px 16px;text-align:left;border-bottom:2px solid #1a1a2e;"
        f"font-weight:700;'>Description</th>"
        f"</tr></thead>"
        f"<tbody>{rows}</tbody>"
        f"</table>"
    )
    _check_token_size("scope_html", result)
    return result


def render_timeline_html(timeline: list[TimelinePhase]) -> str:
    """Render timeline phases as a styled HTML section."""
    phases = ""
    for i, phase in enumerate(timeline, 1):
        deliverables_list = "".join(
            f"<li>{_esc(d)}</li>" for d in phase.deliverables
        )
        phases += (
            f"<div style='margin-bottom:24px;padding:16px;border-left:4px solid #6366f1;"
            f"background:#f8f9fa;border-radius:0 8px 8px 0;'>"
            f"<h3 style='margin:0 0 4px 0;'>Phase {i}: {_esc(phase.phase)}</h3>"
            f"<p style='margin:0 0 8px 0;color:#6b7280;font-size:14px;'>"
            f"Duration: {_esc(phase.duration)}</p>"
            f"<ul style='margin:0;padding-left:20px;'>{deliverables_list}</ul>"
            f"</div>"
        )
    result = f"<h2>Timeline</h2>{phases}"
    _check_token_size("timeline_html", result)
    return result


def render_list_html(items: list[str], ordered: bool = False, title: str = "") -> str:
    """Render a list of strings as an HTML ordered or unordered list."""
    tag = "ol" if ordered else "ul"
    items_html = "".join(
        f"<li style='margin-bottom:8px;'>{_esc(item)}</li>" for item in items
    )
    header = f"<h2>{_esc(title)}</h2>" if title else ""
    result = f"{header}<{tag} style='padding-left:20px;'>{items_html}</{tag}>"
    _check_token_size(title or "list", result)
    return result


def _check_token_size(name: str, value: str) -> None:
    """Warn if a rendered token exceeds the safe size limit."""
    if len(value) > MAX_TOKEN_SIZE:
        logger = logging.getLogger(__name__)
        logger.warning(
            "Token '%s' is %d chars (limit %d) — may be truncated by Qwilr",
            name, len(value), MAX_TOKEN_SIZE,
        )
