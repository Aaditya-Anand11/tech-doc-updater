"""
Report Generator Module

Generates reports in multiple formats: Summary text, JSON, HTML.
Extracted from ComprehensiveReportGenerator in app_main.py.
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Optional

from docsync.models import ProcessingResult, ValidationStatus

logger = logging.getLogger("docsync.report_generator")


class ReportGenerator:
    """
    Generates multi-format reports from processing results.
    Supports: text summary, JSON, HTML.
    """

    def __init__(self, output_dir: str = "./data/output"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    # ── Text Summary ─────────────────────────────────────────

    def generate_summary(self, result: ProcessingResult, pdf_info: Dict) -> str:
        """Generate human-readable text summary"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if result.overall_confidence >= 0.8:
            status = "✅ EXCELLENT"
            status_desc = "High confidence - all changes verified"
        elif result.overall_confidence >= 0.6:
            status = "⚠️ GOOD"
            status_desc = "Moderate confidence - review recommended"
        else:
            status = "❌ NEEDS REVIEW"
            status_desc = "Low confidence - manual review required"

        summary = f"""
╔══════════════════════════════════════════════════════════════════════════╗
║               DOCUMENT UPDATE SUMMARY - TECH DOC AUTO UPDATER            ║
╚══════════════════════════════════════════════════════════════════════════╝

📅 Generated: {timestamp}
📄 Document: {pdf_info.get('title', 'Unknown')}
📊 Status: {status}
   {status_desc}

═══════════════════════════════════════════════════════════════════════════
                              PROCESSING RESULTS
═══════════════════════════════════════════════════════════════════════════

📸 IMAGE UPDATES
────────────────
• Screenshots Processed: {len(result.matches)}
• Images Replaced: {result.images_replaced}
• Match Confidence: {result.overall_confidence:.1%}

📝 TEXT UPDATES
───────────────
• Text Changes Applied: {result.text_replaced}
• Text Changes Detected: {len(result.text_changes)}

⏱️ PERFORMANCE
──────────────
• Processing Time: {result.processing_time:.2f}s
• Pages Processed: {pdf_info.get('pages', 'N/A')}

═══════════════════════════════════════════════════════════════════════════
                              MATCH DETAILS
═══════════════════════════════════════════════════════════════════════════
"""

        for match in result.matches:
            status_icon = "✅" if match.validation_status == ValidationStatus.APPROVED else \
                         "⚠️" if match.validation_status == ValidationStatus.REVIEW else "❌"
            matched_page = match.matched_pdf_image.get('page', 'N/A') if match.matched_pdf_image else 'N/A'

            summary += f"""
{status_icon} {match.new_image_name}
   → Page: {matched_page}
   → Confidence: {match.confidence:.1%}
   → Status: {match.validation_status.value}
"""

        if result.errors:
            summary += "\n❌ ERRORS\n─────────\n"
            for error in result.errors:
                summary += f"• {error}\n"

        if result.warnings:
            summary += "\n⚠️ WARNINGS\n───────────\n"
            for warning in result.warnings:
                summary += f"• {warning}\n"

        summary += f"""
═══════════════════════════════════════════════════════════════════════════
✅ OUTPUT: {result.output_path}
═══════════════════════════════════════════════════════════════════════════
"""
        return summary

    # ── JSON Report ──────────────────────────────────────────

    def generate_json(self, result: ProcessingResult, pdf_info: Dict) -> str:
        """Generate JSON report"""
        data = {
            "timestamp": datetime.now().isoformat(),
            "document": pdf_info,
            "success": result.success,
            "images_replaced": result.images_replaced,
            "text_replaced": result.text_replaced,
            "confidence": result.overall_confidence,
            "processing_time": result.processing_time,
            "matches": [
                {
                    "image": m.new_image_name,
                    "page": m.matched_pdf_image.get("page") if m.matched_pdf_image else None,
                    "confidence": m.confidence,
                    "status": m.validation_status.value,
                }
                for m in result.matches
            ],
            "text_changes": [
                {
                    "old": c.old_text,
                    "new": c.new_text,
                    "confidence": c.confidence,
                }
                for c in result.text_changes
            ],
            "errors": result.errors,
            "warnings": result.warnings,
        }
        return json.dumps(data, indent=2)

    # ── HTML Report ──────────────────────────────────────────

    def generate_html(self, result: ProcessingResult, pdf_info: Dict) -> str:
        """Generate styled HTML report"""
        confidence_pct = result.overall_confidence * 100
        status_color = "#27ae60" if confidence_pct >= 70 else "#f39c12" if confidence_pct >= 50 else "#e74c3c"
        status_text = "PASSED" if confidence_pct >= 70 else "REVIEW NEEDED" if confidence_pct >= 50 else "FAILED"

        matches_html = ""
        for m in result.matches:
            icon = "✅" if m.validation_status == ValidationStatus.APPROVED else \
                   "⚠️" if m.validation_status == ValidationStatus.REVIEW else "❌"
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

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Document Update Report</title>
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
        .progress {{ background: #0f3460; border-radius: 15px; height: 35px; overflow: hidden; margin: 20px 0; }}
        .progress-bar {{ height: 100%; background: linear-gradient(90deg, #4CAF50, #8BC34A); display: flex; align-items: center; justify-content: center; font-weight: bold; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
        th {{ background: #4CAF50; padding: 15px; text-align: left; }}
        td {{ padding: 15px; border-bottom: 1px solid #333; }}
        tr:hover {{ background: #0f3460; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📄 Document Update Report</h1>
            <p>DocSync Engine v3.0</p>
            <p style="color: #888; margin-top: 10px;">{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
            <div class="status-badge">{status_text}</div>
        </div>
        
        <div class="card">
            <h2>📊 Processing Summary</h2>
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
            
            <h3 style="margin-top: 25px;">Overall Confidence</h3>
            <div class="progress">
                <div class="progress-bar" style="width: {confidence_pct}%">{confidence_pct:.0f}%</div>
            </div>
        </div>
        
        <div class="card">
            <h2>🔍 Match Details</h2>
            <table>
                <tr><th>Screenshot</th><th>Matched To</th><th>Confidence</th><th>Status</th></tr>
                {matches_html}
            </table>
        </div>
        
        <div class="card">
            <h2>✅ Output</h2>
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

    def save_json_report(self, json_str: str, filename: str = None) -> str:
        """Save JSON report to file"""
        if filename is None:
            filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(json_str)
        return filepath
