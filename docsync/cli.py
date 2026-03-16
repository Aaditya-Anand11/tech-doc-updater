"""
DocSync CLI Interface

Command-line interface for document processing, comparison,
history management, and administration.
"""

import os
import sys
import time
import json
import argparse
import logging

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from docsync.config import DocSyncConfig
from docsync.logging_config import setup_logging
from docsync.core.doc_parser import DocumentParser
from docsync.core.image_comparator import ImageComparator
from docsync.core.text_processor import SmartTextProcessor
from docsync.core.doc_updater import DocumentUpdater
from docsync.core.validation_engine import ValidationEngine
from docsync.core.report_generator import ReportGenerator
from docsync.core.history_manager import HistoryManager
from docsync.core.visual_analyzer import VisualAnalyzer
from docsync.core.change_analyzer import ChangeAnalyzer
from docsync.plugins.plugin_base import PluginRegistry


def cmd_process(args, config: DocSyncConfig):
    """Process a document update"""
    start = time.time()
    print(f"\n📄 Processing: {args.pdf}")
    print(f"   Old screenshot: {args.old}")
    if args.new:
        print(f"   New screenshot: {args.new}")

    parser = DocumentParser()
    comparator = ImageComparator()
    text_proc = SmartTextProcessor()
    updater = DocumentUpdater()
    report_gen = ReportGenerator(config.output_dir)
    history = HistoryManager(config.history_dir)

    # Pipeline
    pdf_info = parser.get_pdf_info(args.pdf)
    pdf_images = parser.extract_all_images(args.pdf)

    compare_paths = [args.new] if args.new else [args.old]
    matches = comparator.find_best_matches(compare_paths, pdf_images)

    text_changes = []
    if args.new:
        diff = text_proc.find_text_differences(args.old, args.new)
        text_changes = text_proc.generate_text_replacements(diff)

    image_repls = []
    for m in matches:
        if m.is_good_match and m.matched_pdf_image:
            image_repls.append({
                "xref": m.matched_pdf_image["xref"],
                "new_image_path": m.new_image_path,
            })

    output_path = args.output or os.path.join(config.output_dir, "updated_output.pdf")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    result_dict = updater.replace_images_and_text(
        args.pdf, image_repls, text_changes, output_path
    )

    from docsync.models import ProcessingResult
    result = ProcessingResult(
        success=result_dict.get("success", False),
        output_path=output_path,
        images_replaced=result_dict.get("images_replaced", 0),
        text_replaced=result_dict.get("text_replaced", 0),
        matches=matches,
        text_changes=text_changes,
        overall_confidence=sum(m.confidence for m in matches) / max(len(matches), 1),
        processing_time=time.time() - start,
    )

    # Summary
    summary = report_gen.generate_summary(result, pdf_info)
    print(summary)

    # Save reports
    if args.json:
        json_report = report_gen.generate_json(result, pdf_info)
        report_gen.save_json_report(json_report)
        print(f"📊 JSON report saved")

    if args.html:
        html_report = report_gen.generate_html(result, pdf_info)
        report_gen.save_html_report(html_report)
        print(f"📊 HTML report saved")

    history.add_version(args.pdf, {}, result)
    parser.cleanup()


def cmd_compare(args, config: DocSyncConfig):
    """Quick image comparison"""
    comparator = ImageComparator()
    scores = comparator.compute_combined_score(args.image1, args.image2)

    print(f"\n🔍 Image Comparison Results")
    print(f"{'='*40}")
    print(f"  SSIM:       {scores['ssim']:.1%}")
    print(f"  Histogram:  {scores['histogram']:.1%}")
    print(f"  Edge:       {scores['edge']:.1%}")
    print(f"  Template:   {scores['template']:.1%}")
    print(f"  OCR:        {scores.get('ocr', 0):.1%}")
    print(f"  Combined:   {scores['combined']:.1%}")
    print(f"  Match:      {'✅ Yes' if scores['is_match'] else '❌ No'}")


def cmd_history(args, config: DocSyncConfig):
    """Show version history"""
    history = HistoryManager(config.history_dir)
    print(history.get_formatted_history())


def cmd_rollback(args, config: DocSyncConfig):
    """Rollback to a version"""
    history = HistoryManager(config.history_dir)
    result = history.rollback(args.version)
    if result:
        print(f"✅ Rolled back to version {args.version}: {result}")
    else:
        print(f"❌ Version {args.version} not found")


def cmd_plugins(args, config: DocSyncConfig):
    """List available plugins"""
    registry = PluginRegistry()
    try:
        registry.discover_builtin()
    except Exception:
        pass

    plugins = registry.list_plugins()
    print(f"\n🔌 Registered Plugins ({len(plugins)})")
    print(f"{'='*50}")
    for p in plugins:
        status = p["health"]["status"]
        icon = "✅" if status == "ok" else "❌"
        print(f"  {icon} {p['name']} v{p['version']} - {p['description']}")


def cmd_serve(args, config: DocSyncConfig):
    """Start the REST API server"""
    try:
        import uvicorn
        from docsync.api.routes import create_app

        host = args.host or config.api_host
        port = args.port or config.api_port
        app = create_app(config)
        print(f"\n🚀 Starting DocSync API on {host}:{port}")
        uvicorn.run(app, host=host, port=port)
    except ImportError:
        print("❌ FastAPI/Uvicorn not installed. Run: pip install fastapi uvicorn")


def main():
    parser = argparse.ArgumentParser(
        prog="docsync",
        description="DocSync – Documentation Synchronization Engine CLI",
    )
    parser.add_argument("--config", default="config.json",
                        help="Path to config file")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable verbose output")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # process
    p_process = subparsers.add_parser("process", help="Process document update")
    p_process.add_argument("--old", required=True, help="Old/current screenshot path")
    p_process.add_argument("--pdf", required=True, help="PDF document path")
    p_process.add_argument("--new", help="New screenshot path (optional)")
    p_process.add_argument("--output", "-o", help="Output PDF path")
    p_process.add_argument("--json", action="store_true", help="Generate JSON report")
    p_process.add_argument("--html", action="store_true", help="Generate HTML report")

    # compare
    p_compare = subparsers.add_parser("compare", help="Compare two images")
    p_compare.add_argument("image1", help="First image path")
    p_compare.add_argument("image2", help="Second image path")

    # history
    subparsers.add_parser("history", help="Show version history")

    # rollback
    p_rollback = subparsers.add_parser("rollback", help="Rollback to a version")
    p_rollback.add_argument("version", type=int, help="Version ID to rollback to")

    # plugins
    subparsers.add_parser("plugins", help="List available plugins")

    # serve
    p_serve = subparsers.add_parser("serve", help="Start REST API server")
    p_serve.add_argument("--host", default=None, help="API host")
    p_serve.add_argument("--port", type=int, default=None, help="API port")

    args = parser.parse_args()

    # Setup
    config = DocSyncConfig.load(args.config)
    log_level = logging.DEBUG if args.verbose else logging.INFO
    setup_logging(level=log_level)

    # Route to subcommand
    commands = {
        "process": cmd_process,
        "compare": cmd_compare,
        "history": cmd_history,
        "rollback": cmd_rollback,
        "plugins": cmd_plugins,
        "serve": cmd_serve,
    }

    if args.command in commands:
        commands[args.command](args, config)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
