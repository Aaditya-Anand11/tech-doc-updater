"""
DocSync Main Orchestrator

Entry point that ties all modules together and serves the dashboard.
Can run either the API server with dashboard, or the legacy Gradio app.
"""

import os
import sys
import argparse
import logging

# Ensure package root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from docsync.config import DocSyncConfig
from docsync.logging_config import setup_logging


def run_api_server(config: DocSyncConfig):
    """Start the FastAPI server with dashboard"""
    try:
        import uvicorn
        from fastapi.staticfiles import StaticFiles
        from docsync.api.routes import create_app

        app = create_app(config)

        # Serve dashboard static files
        dashboard_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "dashboard"
        )
        if os.path.exists(dashboard_dir):
            app.mount("/", StaticFiles(directory=dashboard_dir, html=True), name="dashboard")

        print(f"""
╔═══════════════════════════════════════════════════════╗
║          ⚡ DocSync Engine v4.0                       ║
╠═══════════════════════════════════════════════════════╣
║  Dashboard:  http://{config.api_host}:{config.api_port}        ║
║  API Docs:   http://{config.api_host}:{config.api_port}/docs   ║
╚═══════════════════════════════════════════════════════╝
        """)

        uvicorn.run(app, host=config.api_host, port=config.api_port)

    except ImportError as e:
        print(f"Error: {e}")
        print("Install required packages: pip install fastapi uvicorn python-multipart")
        sys.exit(1)


def run_legacy_gradio():
    """Run the original Gradio-based app (for backward compatibility)"""
    legacy_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "app_main.py"
    )
    if os.path.exists(legacy_path):
        print("Starting legacy Gradio interface...")
        import importlib.util
        spec = importlib.util.spec_from_file_location("app_main", legacy_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if hasattr(module, 'main'):
            module.main()
    else:
        print("Legacy app_main.py not found")


def main():
    parser = argparse.ArgumentParser(
        description="DocSync – Documentation Synchronization Engine"
    )
    parser.add_argument(
        "--mode", choices=["api", "legacy", "cli"],
        default="api",
        help="Run mode: api (dashboard + REST), legacy (Gradio), cli (command line)"
    )
    parser.add_argument("--config", default="config.json", help="Config file path")
    parser.add_argument("--host", default=None, help="API host override")
    parser.add_argument("--port", type=int, default=None, help="API port override")
    parser.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args()

    config = DocSyncConfig.load(args.config)
    if args.host:
        config.api_host = args.host
    if args.port:
        config.api_port = args.port

    level = logging.DEBUG if args.verbose else logging.INFO
    setup_logging(level=level)

    if args.mode == "api":
        run_api_server(config)
    elif args.mode == "legacy":
        run_legacy_gradio()
    elif args.mode == "cli":
        from docsync.cli import main as cli_main
        cli_main()


if __name__ == "__main__":
    main()
