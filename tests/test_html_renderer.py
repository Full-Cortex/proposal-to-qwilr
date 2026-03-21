"""Tests for HTML rendering functions."""
from proposal_qwilr.schemas import ScopeItem, TimelinePhase
from proposal_qwilr.html_renderer import (
    render_scope_html,
    render_timeline_html,
    render_list_html,
)


class TestRenderScopeHtml:
    def test_renders_table_with_items(self):
        scope = [
            ScopeItem(deliverable="UX Audit", description="Full audit of user flows"),
            ScopeItem(deliverable="Design System", description="Component library"),
        ]
        html = render_scope_html(scope)
        assert "<table" in html
        assert "UX Audit" in html
        assert "Full audit of user flows" in html
        assert "Design System" in html
        assert "Scope &amp; Deliverables" in html

    def test_empty_scope(self):
        html = render_scope_html([])
        assert "<table" in html
        assert "<tbody></tbody>" in html

    def test_xss_escaped(self):
        scope = [
            ScopeItem(
                deliverable='<script>alert("xss")</script>',
                description='<img src=x onerror="alert(1)">',
            ),
        ]
        html = render_scope_html(scope)
        # Raw tags must be escaped — no executable HTML
        assert "<script>" not in html
        assert "<img src=x" not in html
        assert "&lt;script&gt;" in html
        assert "&lt;img" in html


class TestRenderTimelineHtml:
    def test_renders_phases(self):
        timeline = [
            TimelinePhase(
                phase="Discovery",
                duration="2 weeks",
                deliverables=["Interviews", "Audit report"],
            ),
            TimelinePhase(
                phase="Design",
                duration="3 weeks",
                deliverables=["Wireframes"],
            ),
        ]
        html = render_timeline_html(timeline)
        assert "Phase 1: Discovery" in html
        assert "2 weeks" in html
        assert "Interviews" in html
        assert "Phase 2: Design" in html
        assert "Timeline" in html

    def test_empty_timeline(self):
        html = render_timeline_html([])
        assert "Timeline" in html


class TestRenderListHtml:
    def test_unordered_list(self):
        html = render_list_html(["Item A", "Item B"], title="Why Us")
        assert "<ul" in html
        assert "Item A" in html
        assert "Why Us" in html

    def test_ordered_list(self):
        html = render_list_html(["Step 1", "Step 2"], ordered=True, title="Next Steps")
        assert "<ol" in html
        assert "Step 1" in html

    def test_no_title(self):
        html = render_list_html(["X"], title="")
        assert "<h2>" not in html

    def test_empty_list(self):
        html = render_list_html([])
        assert "<ul" in html
