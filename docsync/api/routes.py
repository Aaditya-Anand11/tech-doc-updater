"""
DocSync REST API

FastAPI-based REST API with rate limiting, file upload,
and endpoints for all core operations.
"""

import os
import json
import time
import shutil
import secrets
import tempfile
import logging
from typing import Optional, List, Dict

logger = logging.getLogger("docsync.api")

try:
    from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Query, Request
    from fastapi.responses import FileResponse, JSONResponse
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

from docsync.config import DocSyncConfig
from docsync.models import ProcessingResult
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
from docsync.auth.rbac import RBACManager


def create_app(config: DocSyncConfig = None) -> "FastAPI":
    """Create and configure the FastAPI application"""
    if not FASTAPI_AVAILABLE:
        raise ImportError("FastAPI not installed. Run: pip install fastapi uvicorn python-multipart")

    if config is None:
        config = DocSyncConfig.load()

    app = FastAPI(
        title="DocSync API",
        version="3.0.0",
        description="Documentation Synchronization Engine – REST API",
    )

    # CORS — restrict to local development origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:7870",
            "http://127.0.0.1:7870",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Shared instances
    parser = DocumentParser()
    gemini_cfg = {
        "enabled": config.gemini_enabled,
        "api_key": config.gemini_api_key,
        "model": config.gemini_model,
        "weight": config.gemini_weight,
    }
    ollama_cfg = {
        "enabled": config.ollama_enabled,
        "base_url": config.ollama_base_url,
        "vision_model": config.ollama_vision_model,
        "weight": 0.25,
    }
    comparator = ImageComparator(gemini_config=gemini_cfg, ollama_config=ollama_cfg)
    text_proc = SmartTextProcessor()
    updater = DocumentUpdater()
    validator = ValidationEngine()
    report_gen = ReportGenerator(config.output_dir)
    history = HistoryManager(config.history_dir, config.max_versions)
    analyzer = ChangeAnalyzer()
    visual = VisualAnalyzer()

    # Track last generated output for download
    last_output = {"pdf": None, "report": None}

    # Plugin registry
    registry = PluginRegistry()
    try:
        registry.discover_builtin()
    except Exception:
        pass

    # Auth manager & session store
    rbac = RBACManager()
    sessions: Dict[str, Dict] = {}  # token -> {user info + "_created": timestamp}
    SESSION_TTL = 3600 * 8  # 8-hour session lifetime

    def _cleanup_expired_sessions():
        """Remove sessions older than SESSION_TTL"""
        now = time.time()
        expired = [t for t, s in sessions.items() if now - s.get("_created", 0) > SESSION_TTL]
        for t in expired:
            sessions.pop(t, None)

    class LoginRequest(BaseModel):
        username: str
        password: str

    class CreateUserRequest(BaseModel):
        username: str
        password: str
        role: str = "viewer"

    def get_current_user(request: Request) -> Optional[Dict]:
        """Extract user from Authorization header"""
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
            return sessions.get(token)
        return None

    def require_user(request: Request) -> Dict:
        """Require authenticated user"""
        user = get_current_user(request)
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return user

    def require_admin(request: Request) -> Dict:
        """Require admin role"""
        user = require_user(request)
        if user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")
        return user

    # ── Endpoints ────────────────────────────────────────

    @app.get("/health")
    async def health():
        return {"status": "ok", "version": "3.0.0", "plugins": registry.list_plugins()}

    # ─── Auth ───────────────────────────────────────────

    @app.post("/api/auth/login")
    async def login(body: LoginRequest):
        user = rbac.authenticate(body.username, body.password)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        _cleanup_expired_sessions()
        token = secrets.token_hex(32)
        sessions[token] = {**user, "_created": time.time()}
        return {"token": token, "user": user}

    @app.get("/api/auth/me")
    async def get_me(request: Request):
        user = require_user(request)
        return {"user": user}

    @app.get("/api/auth/users")
    async def list_users(request: Request):
        require_admin(request)
        return {"users": rbac.list_users()}

    @app.post("/api/auth/users")
    async def create_user(body: CreateUserRequest, request: Request):
        require_admin(request)
        ok = rbac.create_user(body.username, body.password, body.role)
        if not ok:
            raise HTTPException(status_code=400, detail="User already exists or invalid role")
        return {"success": True}

    @app.post("/api/auth/logout")
    async def logout(request: Request):
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            sessions.pop(auth[7:], None)
        return {"success": True}

    # ─── Plugins ────────────────────────────────────────

    @app.get("/api/plugins")
    async def list_plugins():
        return {"plugins": registry.list_all_plugins()}

    @app.post("/api/plugins/{name}/toggle")
    async def toggle_plugin(name: str, request: Request):
        require_admin(request)
        new_state = registry.toggle_plugin(name)
        return {"plugin": name, "enabled": new_state}

    # Pending process sessions: session_id -> { tmp, pdf_path, matches_data, ... }
    pending_sessions: Dict[str, Dict] = {}

    @app.post("/api/process")
    async def process_document(
        pdf_document: UploadFile = File(...),
        new_screenshots: List[UploadFile] = File(...),
        old_screenshot: UploadFile = File(None),
    ):
        """
        Phase 1: Upload, extract, match — return match preview (don't apply yet).
        The user reviews matches and then calls /api/process/apply.
        """
        start = time.time()
        tmp = tempfile.mkdtemp()

        try:
            # Save PDF
            pdf_path = os.path.join(tmp, pdf_document.filename)
            with open(pdf_path, "wb") as f:
                shutil.copyfileobj(pdf_document.file, f)

            # Save new screenshots (required)
            new_paths = []
            for idx, ns in enumerate(new_screenshots):
                if ns and ns.filename and ns.size and ns.size > 0:
                    safe_name = f"new_{idx}_{ns.filename}"
                    np_path = os.path.join(tmp, safe_name)
                    with open(np_path, "wb") as f:
                        shutil.copyfileobj(ns.file, f)
                    new_paths.append(np_path)

            # Save old screenshot (optional, for text diffing)
            old_path = None
            if old_screenshot and old_screenshot.filename and old_screenshot.size and old_screenshot.size > 0:
                old_path = os.path.join(tmp, old_screenshot.filename)
                with open(old_path, "wb") as f:
                    shutil.copyfileobj(old_screenshot.file, f)

            # ── Pipeline: match only (don't apply) ──
            pdf_info = parser.get_pdf_info(pdf_path)
            logger.info(f"PDF: {pdf_info.get('pages', '?')} pages, "
                        f"{pdf_info.get('total_images', '?')} images")
            extract_dir = os.path.join(tmp, "extracted")
            pdf_images = parser.extract_all_images(pdf_path, output_dir=extract_dir)
            logger.info(f"Extracted {len(pdf_images)} images, starting matching...")

            # CRITICAL: Match OLD screenshot against PDF to find WHERE
            # the image is, then replace with the NEW screenshot.
            # If no old screenshot, fall back to matching new (compare mode).
            match_sources = [old_path] if old_path else new_paths
            all_matches = comparator.find_best_matches(match_sources, pdf_images)

            # If we matched old_gui, set the new_gui as the replacement image
            if old_path and new_paths:
                for m in all_matches:
                    if m.is_good_match:
                        m.new_image_path = new_paths[0]
                        m.new_image_name = os.path.basename(new_paths[0])

            # Fallback: if no match with extracted images, try rendered pages
            if not any(m.is_good_match for m in all_matches):
                logger.info("No match with extracted images, trying rendered PDF pages...")
                render_dir = os.path.join(tmp, "rendered")
                rendered_pages = parser.render_pdf_pages(pdf_path, output_dir=render_dir)
                if rendered_pages:
                    page_matches = comparator.find_best_matches(match_sources, rendered_pages)
                    for pm in page_matches:
                        if pm.is_good_match:
                            target_page = pm.matched_pdf_image.get("page")
                            page_imgs = [i for i in pdf_images if i.get("page") == target_page]
                            if page_imgs:
                                from docsync.models import MatchResult
                                match = MatchResult(
                                    new_image_path=new_paths[0] if new_paths else match_sources[0],
                                    new_image_name=os.path.basename(new_paths[0]) if new_paths else "old_gui",
                                    matched_pdf_image=page_imgs[0],
                                    is_good_match=True,
                                    target_page=target_page,
                                    confidence=pm.confidence,
                                    combined_score=pm.combined_score,
                                )
                                all_matches = [match]
                                break

            # Text differences (only if old screenshot provided)
            all_text_changes = []
            all_color_changes = []
            color_summary = {}
            if old_path:
                for np in new_paths:
                    try:
                        diff = text_proc.find_text_differences(old_path, np)
                        changes = text_proc.generate_text_replacements(diff)
                        all_text_changes.extend(changes)
                    except Exception as e:
                        logger.warning(f"Text diff failed for {np}: {e}")

                    # Color detection between old and new screenshots
                    try:
                        cc = visual.detect_color_changes(old_path, np)
                        all_color_changes.extend(cc)
                        cs = visual.get_overall_color_summary(old_path, np)
                        if cs:
                            color_summary = cs
                    except Exception as e:
                        logger.warning(f"Color detection failed for {np}: {e}")

            # Validate matches
            for m in all_matches:
                if m.matched_pdf_image:
                    val_result = validator.validate_image_match(
                        m, m.matched_pdf_image.get("path", "")
                    )
                    m.validation_status = val_result["status"]
                    m.confidence = val_result["confidence"]
                    m.issues = val_result.get("issues", [])

            # Build per-match details for frontend review
            matches_detail = []
            for idx, m in enumerate(all_matches):
                page = m.matched_pdf_image.get("page", "?") if m.matched_pdf_image else "?"
                xref = m.matched_pdf_image.get("xref") if m.matched_pdf_image else None
                status = m.validation_status.value if hasattr(m.validation_status, 'value') else str(m.validation_status)
                matches_detail.append({
                    "index": idx,
                    "screenshot_name": m.new_image_name,
                    "page": page,
                    "xref": xref,
                    "confidence": round(m.confidence * 100, 1),
                    "combined_score": round(m.combined_score, 4),
                    "status": status,
                    "is_good_match": m.is_good_match,
                    "scores": {
                        "ssim": round(m.similarity_score, 4),
                        "histogram": round(m.histogram_score, 4),
                        "edge": round(m.edge_score, 4),
                        "template": round(m.template_score, 4),
                        "ocr": round(getattr(m, 'ocr_score', 0), 4),
                    },
                    "issues": m.issues,
                })

            # Store session for Phase 2 (don't clean up tmp yet!)
            session_id = secrets.token_hex(16)
            pending_sessions[session_id] = {
                "tmp": tmp,
                "pdf_path": pdf_path,
                "pdf_info": pdf_info,
                "all_matches": all_matches,
                "all_text_changes": all_text_changes,
                "all_color_changes": all_color_changes,
                "color_summary": color_summary,
                "new_paths": new_paths,
                "old_path": old_path,
                "created": time.time(),
            }

            overall_conf = sum(m.confidence for m in all_matches) / max(len(all_matches), 1)

            # Serialize text changes for frontend review
            text_changes_detail = []
            for i, tc in enumerate(all_text_changes):
                text_changes_detail.append({
                    "index": i,
                    "old_text": tc.old_text,
                    "new_text": tc.new_text,
                    "page": tc.page,
                    "confidence": round(tc.confidence * 100, 1),
                    "context": tc.context,
                    "approved": tc.approved,
                })

            # Serialize color changes (top 15)
            color_changes_detail = all_color_changes[:15]

            return JSONResponse({
                "session_id": session_id,
                "screenshots_uploaded": len(new_paths),
                "matches": matches_detail,
                "text_changes_found": len(all_text_changes),
                "text_changes": text_changes_detail,
                "color_changes": color_changes_detail,
                "color_summary": color_summary,
                "overall_confidence": round(overall_conf * 100, 1),
                "processing_time": round(time.time() - start, 2),
            })

        except Exception as e:
            logger.error(f"Processing error: {e}")
            shutil.rmtree(tmp, ignore_errors=True)
            raise HTTPException(status_code=500, detail="Internal processing error. Check server logs.")

    class ApplyRequest(BaseModel):
        session_id: str
        decisions: List[Dict]  # [{"index": 0, "action": "approve"}, ...]
        text_decisions: List[Dict] = []  # [{"index": 0, "approved": true}, ...]

    @app.post("/api/process/apply")
    async def apply_decisions(body: ApplyRequest):
        """
        Phase 2: Apply user-approved replacements to the PDF.
        Accepts decisions for images and text changes.
        """
        session = pending_sessions.pop(body.session_id, None)
        if not session:
            raise HTTPException(status_code=404, detail="Session expired or not found")

        try:
            all_matches = session["all_matches"]
            pdf_path = session["pdf_path"]
            pdf_info = session["pdf_info"]
            all_text_changes = session["all_text_changes"]
            all_color_changes = session.get("all_color_changes", [])
            color_summary = session.get("color_summary", {})

            # Build a set of approved image indices
            approved_indices = set()
            for d in body.decisions:
                if d.get("action") == "approve":
                    approved_indices.add(d["index"])

            # Apply text change decisions from frontend
            if body.text_decisions:
                for td in body.text_decisions:
                    idx = td.get("index", -1)
                    if 0 <= idx < len(all_text_changes):
                        all_text_changes[idx].approved = td.get("approved", all_text_changes[idx].approved)

            # Build image replacements from approved matches only
            image_repls = []
            used_xrefs = set()
            approved_count = 0
            for idx, m in enumerate(all_matches):
                if idx in approved_indices and m.matched_pdf_image:
                    xref = m.matched_pdf_image["xref"]
                    if xref not in used_xrefs:
                        image_repls.append({
                            "xref": xref,
                            "new_image_path": m.new_image_path,
                        })
                        used_xrefs.add(xref)
                        approved_count += 1
                        logger.info(f"Approved: {m.new_image_name} -> PDF xref={xref} "
                                    f"(page {m.matched_pdf_image.get('page', '?')})")

            output_pdf = os.path.join(config.output_dir, "updated_output.pdf")
            os.makedirs(config.output_dir, exist_ok=True)
            update_result = updater.replace_images_and_text(
                pdf_path, image_repls, all_text_changes, output_pdf
            )

            # Build processing result
            result = ProcessingResult(
                success=update_result.get("success", False),
                output_path=output_pdf,
                images_replaced=update_result.get("images_replaced", 0),
                text_replaced=update_result.get("text_replaced", 0),
                matches=all_matches,
                text_changes=all_text_changes,
                overall_confidence=sum(m.confidence for m in all_matches) / max(len(all_matches), 1),
                processing_time=0,
            )

            # Generate summary report (with color changes)
            summary = report_gen.generate_summary(
                result, pdf_info,
                color_changes=all_color_changes,
                color_summary=color_summary,
            )

            # Save summary report to file
            report_path = report_gen.save_summary_report(summary)
            last_output["report"] = os.path.abspath(report_path)

            # History
            history.add_version(pdf_path, {}, result)

            # Store for download
            last_output["pdf"] = os.path.abspath(output_pdf)

            # Serialize text changes for the response
            text_changes_applied = []
            for tc in all_text_changes:
                text_changes_applied.append({
                    "old_text": tc.old_text,
                    "new_text": tc.new_text,
                    "page": tc.page,
                    "applied": tc.approved,
                    "confidence": round(tc.confidence * 100, 1),
                })

            return JSONResponse({
                "success": result.success,
                "images_replaced": result.images_replaced,
                "text_replaced": result.text_replaced,
                "approved_count": approved_count,
                "rejected_count": len(all_matches) - approved_count,
                "output_pdf": os.path.abspath(output_pdf),
                "summary": summary,
                "text_changes_applied": text_changes_applied,
                "color_changes": all_color_changes[:15],
                "color_summary": color_summary,
            })

        except Exception as e:
            logger.error(f"Apply error: {e}")
            raise HTTPException(status_code=500, detail="Internal processing error. Check server logs.")
        finally:
            shutil.rmtree(session.get("tmp", ""), ignore_errors=True)

    @app.get("/api/process/{session_id}/preview/{kind}/{index}")
    async def preview_image(session_id: str, kind: str, index: int):
        """
        Serve preview images from a pending processing session.
        kind: 'uploaded' (new screenshot) or 'matched' (PDF image it matched to)
        """
        session = pending_sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        all_matches = session["all_matches"]
        if index < 0 or index >= len(all_matches):
            raise HTTPException(status_code=404, detail="Invalid index")

        m = all_matches[index]

        if kind == "uploaded":
            path = m.new_image_path
        elif kind == "matched" and m.matched_pdf_image:
            path = m.matched_pdf_image.get("path", "")
        else:
            logger.warning(f"Preview: no matched image for index {index}, kind={kind}")
            raise HTTPException(status_code=404, detail="No image available")

        logger.info(f"Preview: kind={kind}, index={index}, path={path}, exists={os.path.isfile(path) if path else False}")

        if not path or not os.path.isfile(path):
            raise HTTPException(status_code=404, detail=f"Image file not found: {path}")

        return FileResponse(path)


    @app.get("/api/history")
    async def get_history():
        return {"versions": history.get_history()}

    @app.post("/api/rollback/{version_id}")
    async def rollback(version_id: int):
        result = history.rollback(version_id)
        if result:
            return {"success": True, "restored": result}
        raise HTTPException(status_code=404, detail="Version not found")

    # ─── Gemini settings ─────────────────────────────────
    class GeminiSettingsRequest(BaseModel):
        api_key: str

    @app.post("/api/settings/gemini")
    async def save_gemini_key(body: GeminiSettingsRequest):
        nonlocal comparator
        config.gemini_api_key = body.api_key
        # Auto-enable Gemini when a key is provided
        config.gemini_enabled = bool(body.api_key.strip())
        config.save()
        # Reinitialize comparator with new key and enabled=True
        g = {
            "enabled": config.gemini_enabled,
            "api_key": config.gemini_api_key,
            "model": config.gemini_model,
            "weight": config.gemini_weight,
        }
        o = {
            "enabled": config.ollama_enabled,
            "base_url": config.ollama_base_url,
            "vision_model": config.ollama_vision_model,
            "weight": 0.25,
        }
        comparator = ImageComparator(gemini_config=g, ollama_config=o)
        return {
            "success": True,
            "gemini_available": comparator.ai_name == "Gemini",
            "ai_backend": comparator.ai_name or "none",
        }

    @app.get("/api/settings/gemini")
    async def get_gemini_status():
        return {
            "enabled": config.gemini_enabled,
            "has_key": bool(config.gemini_api_key),
            "model": config.gemini_model,
            "gemini_active": comparator.ai_name == "Gemini",
            "ai_backend": comparator.ai_name or "none",
        }

    @app.post("/api/compare")
    async def compare_images(
        images: List[UploadFile] = File(...),
    ):
        """
        Batch comparison: upload multiple images and automatically
        compare every pair. Returns pairwise similarity scores.
        """
        if len(images) < 2:
            raise HTTPException(status_code=400, detail="Upload at least 2 images")

        tmp = tempfile.mkdtemp()
        try:
            # Save all uploaded images
            paths = []
            names = []
            for idx, img in enumerate(images):
                safe = f"img_{idx}_{img.filename}"
                p = os.path.join(tmp, safe)
                with open(p, "wb") as f:
                    shutil.copyfileobj(img.file, f)
                paths.append(p)
                names.append(img.filename)

            # Compare every pair
            comparisons = []
            for i in range(len(paths)):
                for j in range(i + 1, len(paths)):
                    scores = comparator.compute_combined_score(paths[i], paths[j])
                    comparisons.append({
                        "image_a": names[i],
                        "image_b": names[j],
                        "index_a": i,
                        "index_b": j,
                        "scores": scores,
                    })

            return {
                "total_images": len(paths),
                "total_comparisons": len(comparisons),
                "comparisons": comparisons,
            }
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    @app.get("/api/pdf/info")
    async def pdf_info_endpoint(path: str = Query(...)):
        """Get PDF metadata — path must be under allowed directories"""
        # Security: prevent path traversal attacks
        real_path = os.path.realpath(path)
        allowed_roots = [
            os.path.realpath(config.data_dir),
            os.path.realpath(config.output_dir),
        ]
        if not any(real_path.startswith(root) for root in allowed_roots):
            raise HTTPException(status_code=403, detail="Access denied: path outside allowed directory")
        if not os.path.exists(real_path):
            raise HTTPException(status_code=404, detail="File not found")
        return parser.get_pdf_info(real_path)

    @app.get("/api/download/pdf")
    async def download_pdf():
        """Download the last generated PDF"""
        pdf_path = last_output.get("pdf")
        if not pdf_path or not os.path.exists(pdf_path):
            raise HTTPException(status_code=404, detail="No PDF available. Process a document first.")
        return FileResponse(
            pdf_path,
            filename="updated_output.pdf",
            media_type="application/pdf",
        )

    @app.get("/api/download/report")
    async def download_report():
        """Download the last generated summary report"""
        report_path = last_output.get("report")
        if not report_path or not os.path.exists(report_path):
            raise HTTPException(status_code=404, detail="No report available. Process a document first.")
        return FileResponse(
            report_path,
            filename="change_summary_report.txt",
            media_type="text/plain",
        )

    return app
