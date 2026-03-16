"""
Report Generator Module

Generates change summary reports showing what changed, where (page/section),
including text changes and color changes with RGB/hex values.
"""

import os
import logging
from datetime import datetime
from typing import Dict, List, Optional

from docsync.models import ProcessingResult, ValidationStatus

logger = logging.getLogger("docsync.report_generator")


class ReportGenerator:
    """
    Generates detailed change summary reports from processing results.
    Reports include: page-level changes, text changes, color changes (RGB/hex).
    """

    def __init__(self, output_dir: str = "./data/output"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    # ── Summary Report (main report format) ────────────────

    def generate_summary(self, result: ProcessingResult, pdf_info: Dict,
                         color_changes: List[Dict] = None,
                         color_summary: Dict = None) -> str:
        """
        Generate a human-readable change summary report.
        Includes: what changed, where (page/section), text changes,
        and color changes with RGB and hex values.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        doc_title = pdf_info.get('title', 'Unknown')
        doc_pages = pdf_info.get('pages', 'N/A')

        if result.overall_confidence >= 0.8:
            status = "EXCELLENT"
            status_desc = "High confidence - all changes verified"
        elif result.overall_confidence >= 0.6:
            status = "GOOD"
            status_desc = "Moderate confidence - review recommended"
        else:
            status = "NEEDS REVIEW"
            status_desc = "Low confidence - manual review required"

        lines = []
        lines.append("=" * 70)
        lines.append("  DOCUMENT CHANGE SUMMARY REPORT")
        lines.append("  DocSync Engine v3.0")
        lines.append("=" * 70)
        lines.append(f"  Generated: {timestamp}")
        lines.append(f"  Document:  {doc_title} ({doc_pages} pages)")
        lines.append(f"  Status:    {status} - {status_desc}")
        lines.append("=" * 70)

        # ── Image Changes ──
        lines.append("")
        lines.append("IMAGE CHANGES")
        lines.append("-" * 50)

        if result.matches:
            for m in result.matches:
                status_icon = "[APPROVED]" if m.validation_status == ValidationStatus.APPROVED else \
                              "[REVIEW]" if m.validation_status == ValidationStatus.REVIEW else "[REJECTED]"
                matched_page = m.matched_pdf_image.get('page', 'N/A') if m.matched_pdf_image else 'N/A'

                lines.append(f"  {status_icon} {m.new_image_name}")
                lines.append(f"    Page:       {matched_page}")
                lines.append(f"    Confidence: {m.confidence:.1%}")
                lines.append(f"    Status:     {m.validation_status.value}")
                lines.append("")
        else:
            lines.append("  No image changes detected.")
            lines.append("")

        lines.append(f"  Total Images Replaced: {result.images_replaced}")
        lines.append("")

        # ── Text Changes ──
        lines.append("TEXT CHANGES")
        lines.append("-" * 50)

        if result.text_changes:
            for i, tc in enumerate(result.text_changes, 1):
                approved_tag = "[APPLIED]" if tc.approved else "[SKIPPED]"
                page_info = f"Page {tc.page}" if tc.page else "All pages"
                lines.append(f"  {i}. {approved_tag} ({page_info})")
                lines.append(f"     Old: \"{tc.old_text}\"")
                lines.append(f"     New: \"{tc.new_text}\"")
                lines.append(f"     Confidence: {tc.confidence:.1%}")
                if tc.context:
                    lines.append(f"     Category: {tc.context}")
                lines.append("")
        else:
            lines.append("  No text changes detected.")
            lines.append("")

        lines.append(f"  Total Text Replacements Applied: {result.text_replaced}")
        lines.append("")

        # ── Color Changes ──
        lines.append("COLOR CHANGES")
        lines.append("-" * 50)

        if color_summary:
            shift = color_summary.get("overall_color_shift", 0)
            old_hex = color_summary.get("old_dominant_hex", "N/A")
            new_hex = color_summary.get("new_dominant_hex", "N/A")
            old_rgb = color_summary.get("old_dominant_rgb", "N/A")
            new_rgb = color_summary.get("new_dominant_rgb", "N/A")
            lines.append(f"  Overall Color Shift: {shift:.1f}")
            lines.append(f"  Old Dominant Color: RGB{old_rgb} ({old_hex})")
            lines.append(f"  New Dominant Color: RGB{new_rgb} ({new_hex})")
            lines.append("")

        if color_changes:
            for i, cc in enumerate(color_changes[:15], 1):  # Show top 15
                loc = cc.get("location", "unknown")
                sev = cc.get("severity", "minor").upper()
                old_c = cc.get("old_color", {})
                new_c = cc.get("new_color", {})
                diff = cc.get("color_difference", 0)

                lines.append(f"  {i}. [{sev}] Region at {loc}")
                lines.append(f"     Old Color: RGB{old_c.get('rgb', 'N/A')} ({old_c.get('hex', 'N/A')})")
                lines.append(f"     New Color: RGB{new_c.get('rgb', 'N/A')} ({new_c.get('hex', 'N/A')})")
                lines.append(f"     Color Difference: {diff}")
                lines.append("")
        else:
            lines.append("  No color changes detected (provide old screenshot for color analysis).")
            lines.append("")

        # ── Performance ──
        lines.append("PERFORMANCE")
        lines.append("-" * 50)
        lines.append(f"  Processing Time: {result.processing_time:.2f}s")
        lines.append(f"  Pages Processed: {doc_pages}")
        lines.append("")

        # ── Errors / Warnings ──
        if result.errors:
            lines.append("ERRORS")
            lines.append("-" * 50)
            for error in result.errors:
                lines.append(f"  * {error}")
            lines.append("")

        if result.warnings:
            lines.append("WARNINGS")
            lines.append("-" * 50)
            for warning in result.warnings:
                lines.append(f"  * {warning}")
            lines.append("")

        # ── Output ──
        lines.append("=" * 70)
        lines.append(f"  OUTPUT: {result.output_path}")
        lines.append("=" * 70)

        return "\n".join(lines)

    # ── HTML Report ──────────────────────────────────────────

    def generate_html(self, result: ProcessingResult, pdf_info: Dict,
                      color_changes: List[Dict] = None,
                      color_summary: Dict = None) -> str:
        """Generate styled HTML change summary report"""
        confidence_pct = result.overall_confidence * 100
        status_color = "#27ae60" if confidence_pct >= 70 else "#f39c12" if confidence_pct >= 50 else "#e74c3c"
        status_text = "PASSED" if confidence_pct >= 70 else "REVIEW NEEDED" if confidence_pct >= 50 else "FAILED"

        # Image matches HTML
        matches_html = ""
        for m in result.matches:
            icon = "[OK]" if m.validation_status == ValidationStatus.APPROVED else \
                   "[REVIEW]" if m.validation_status == ValidationStatus.REVIEW else "[FAIL]"
            matched_page = m.matched_pdf_image.get('page', 'N/A') if m.matched_pdf_image else 'N/A'
            confidence_color = '#27ae60' if m.confidence >= 0.7 else '#f39c12'
            matches_html += f"""
            <tr>
                <td>{icon} {m.new_image_name}</td>
                <td>Page {matched_page}</td>
                <td style="color: {confidence_color}">{m.confidence:.1%}</td>
                <td>{m.validation_status.value}</td>
            </tr>
            """

        # Text changes HTML
        text_html = ""
        if result.text_changes:
            for tc in result.text_changes:
                tag = "Applied" if tc.approved else "Skipped"
                tag_color = "#27ae60" if tc.approved else "#888"
                page_info = f"Page {tc.page}" if tc.page else "All pages"
                text_html += f"""
                <tr>
                    <td style="color:{tag_color}">{tag}</td>
                    <td>{page_info}</td>
                    <td><del style="color:#e74c3c">{tc.old_text}</del></td>
                    <td style="color:#27ae60">{tc.new_text}</td>
                    <td>{tc.confidence:.1%}</td>
                </tr>
                """
        else:
            text_html = '<tr><td colspan="5" style="text-align:center;color:#888">No text changes detected</td></tr>'

        # Color changes HTML
        color_html = ""
        if color_changes:
            for cc in color_changes[:15]:
                loc = cc.get("location", "?")
                sev = cc.get("severity", "minor")
                old_c = cc.get("old_color", {})
                new_c = cc.get("new_color", {})
                diff = cc.get("color_difference", 0)
                sev_color = "#e74c3c" if sev == "major" else "#f39c12"
                color_html += f"""
                <tr>
                    <td style="color:{sev_color}">{sev.upper()}</td>
                    <td>{loc}</td>
                    <td>
                        <span style="display:inline-block;width:16px;height:16px;background:{old_c.get('hex','#000')};border:1px solid #333;vertical-align:middle;margin-right:6px;border-radius:3px"></span>
                        RGB{old_c.get('rgb','')} ({old_c.get('hex','')})
                    </td>
                    <td>
                        <span style="display:inline-block;width:16px;height:16px;background:{new_c.get('hex','#000')};border:1px solid #333;vertical-align:middle;margin-right:6px;border-radius:3px"></span>
                        RGB{new_c.get('rgb','')} ({new_c.get('hex','')})
                    </td>
                    <td>{diff}</td>
                </tr>
                """
        else:
            color_html = '<tr><td colspan="5" style="text-align:center;color:#888">No color changes detected</td></tr>'

        # Color summary section
        color_summary_html = ""
        if color_summary:
            old_hex = color_summary.get("old_dominant_hex", "#000")
            new_hex = color_summary.get("new_dominant_hex", "#000")
            shift = color_summary.get("overall_color_shift", 0)
            color_summary_html = f"""
            <div class="stats" style="margin-bottom:20px">
                <div class="stat">
                    <div style="width:40px;height:40px;background:{old_hex};border-radius:8px;margin:0 auto 8px"></div>
                    <div class="stat-label">Old Color {old_hex}</div>
                </div>
                <div class="stat">
                    <div style="width:40px;height:40px;background:{new_hex};border-radius:8px;margin:0 auto 8px"></div>
                    <div class="stat-label">New Color {new_hex}</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{shift:.1f}</div>
                    <div class="stat-label">Color Shift</div>
                </div>
            </div>
            """

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Document Change Summary Report</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #0a0a0a; color: #fff; }}
        .container {{ max-width: 1100px; margin: 0 auto; padding: 30px; }}
        .header {{ background: linear-gradient(135deg, #1a1a2e, #16213e); padding: 40px; border-radius: 15px; text-align: center; margin-bottom: 30px; }}
        .status-badge {{ display: inline-block; padding: 12px 35px; background: {status_color}; border-radius: 30px; font-size: 1.2em; font-weight: bold; margin-top: 20px; }}
        .card {{ background: #16213e; border-radius: 15px; padding: 25px; margin-bottom: 20px; }}
        .card h2 {{ color: #4CAF50; margin-bottom: 20px; padding-bottom: 10px; border-bottom: 2px solid #4CAF50; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 20px; }}
        .stat {{ background: #0f3460; padding: 25px; border-radius: 12px; text-align: center; }}
        .stat-value {{ font-size: 2.5em; font-weight: bold; color: #4CAF50; }}
        .stat-label {{ color: #888; margin-top: 5px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
        th {{ background: #4CAF50; padding: 12px; text-align: left; }}
        td {{ padding: 12px; border-bottom: 1px solid #333; }}
        tr:hover {{ background: #0f3460; }}
        del {{ text-decoration: line-through; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Document Change Summary Report</h1>
            <p>DocSync Engine v3.0</p>
            <p style="color: #888; margin-top: 10px;">{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
            <div class="status-badge">{status_text}</div>
        </div>

        <div class="card">
            <h2>Processing Summary</h2>
            <div class="stats">
                <div class="stat">
                    <div class="stat-value">{len(result.matches)}</div>
                    <div class="stat-label">Screenshots</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{result.images_replaced}</div>
                    <div class="stat-label">Images Replaced</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{result.text_replaced}</div>
                    <div class="stat-label">Text Updates</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{result.processing_time:.1f}s</div>
                    <div class="stat-label">Time</div>
                </div>
            </div>
        </div>

        <div class="card">
            <h2>Image Changes</h2>
            <table>
                <tr><th>Screenshot</th><th>Location</th><th>Confidence</th><th>Status</th></tr>
                {matches_html}
            </table>
        </div>

        <div class="card">
            <h2>Text Changes</h2>
            <table>
                <tr><th>Status</th><th>Page</th><th>Old Text</th><th>New Text</th><th>Confidence</th></tr>
                {text_html}
            </table>
        </div>

        <div class="card">
            <h2>Color Changes</h2>
            {color_summary_html}
            <table>
                <tr><th>Severity</th><th>Location</th><th>Old Color</th><th>New Color</th><th>Difference</th></tr>
                {color_html}
            </table>
        </div>

        <div class="card">
            <h2>Output</h2>
            <p><strong>Updated PDF:</strong> {result.output_path}</p>
            <p><strong>Document:</strong> {pdf_info.get('title', 'N/A')} ({pdf_info.get('pages', 'N/A')} pages)</p>
        </div>
    </div>
</body>
</html>
"""
        return html

    # ── File helpers ─────────────────────────────────────────

    def save_html_report(self, html: str, filename: str = None) -> str:
        """Save HTML report to file"""
        if filename is None:
            filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)
        return filepath

    def save_summary_report(self, summary: str, filename: str = None) -> str:
        """Save summary text report to file"""
        if filename is None:
            filename = f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(summary)
        return filepath
