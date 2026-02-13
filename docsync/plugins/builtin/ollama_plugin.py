"""
Ollama LLM Plugin

Integrates with a locally-running Ollama instance for:
    - Semantic summarization of UI changes
    - Natural-language descriptions of document updates
    - Context-aware text analysis
"""

import json
import logging
from typing import Dict, List, Any, Optional

from docsync.plugins.plugin_base import PluginBase
from docsync.models import MatchResult, TextChange

logger = logging.getLogger("docsync.plugins.ollama")

try:
    import urllib.request
    HTTP_AVAILABLE = True
except ImportError:
    HTTP_AVAILABLE = False


class OllamaLLMPlugin(PluginBase):
    name = "ai_llm"
    version = "1.0.0"
    description = "Ollama LLM integration for semantic analysis and summarization"

    def __init__(self):
        self.base_url = "http://localhost:11434"
        self.model = "llama3"
        self._available = False

    def initialize(self, config: Dict) -> bool:
        """Initialize and check Ollama connection"""
        self.base_url = config.get("ollama_base_url", self.base_url)
        self.model = config.get("ollama_model", self.model)

        # Test connection to Ollama
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags")
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                models = [m.get("name", "") for m in data.get("models", [])]
                if any(self.model in m for m in models):
                    self._available = True
                    logger.info(f"Ollama connected: model '{self.model}' available")
                    return True
                else:
                    logger.warning(
                        f"Ollama connected but model '{self.model}' not found. "
                        f"Available: {models}"
                    )
                    # Still return True — we can try to use it
                    self._available = True
                    return True
        except Exception as e:
            logger.info(f"Ollama not available: {e}")
            self._available = False
            return False

    def execute(self, prompt: str = "", **kwargs) -> Any:
        """Send a prompt to Ollama and return the response"""
        if not self._available:
            return {"error": "Ollama not available", "response": ""}

        try:
            payload = json.dumps({
                "model": self.model,
                "prompt": prompt,
                "stream": False,
            }).encode("utf-8")

            req = urllib.request.Request(
                f"{self.base_url}/api/generate",
                data=payload,
                method="POST",
            )
            req.add_header("Content-Type", "application/json")

            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode())
                return {
                    "response": result.get("response", ""),
                    "model": result.get("model", self.model),
                    "done": result.get("done", False),
                }
        except Exception as e:
            logger.error(f"Ollama generation error: {e}")
            return {"error": str(e), "response": ""}

    def describe_ui_change(
        self,
        match: MatchResult,
        text_changes: List[TextChange],
        regions: List[Dict],
    ) -> Optional[str]:
        """Generate a human-readable description of a UI change using LLM"""
        if not self._available:
            return None

        changes_text = "\n".join(
            f'- "{tc.old_text}" changed to "{tc.new_text}"'
            for tc in text_changes[:5]
        )

        regions_text = "\n".join(
            f"- {r['severity']} change at {r['location']} ({r['area']}px²)"
            for r in regions[:5]
        )

        prompt = f"""You are a technical writer. Describe the following GUI change concisely in 1-2 sentences:

Image match confidence: {match.confidence:.0%}
Text changes:
{changes_text or 'None detected'}

Visual regions changed:
{regions_text or 'None detected'}

Provide a clear, professional summary suitable for a change log."""

        result = self.execute(prompt=prompt)
        return result.get("response") or None

    def summarize_report(self, report_text: str) -> Optional[str]:
        """Generate an executive summary of a processing report"""
        if not self._available:
            return None

        prompt = f"""Summarize the following document update report in 2-3 sentences 
for an executive audience. Focus on what changed and the confidence level.

{report_text[:2000]}"""

        result = self.execute(prompt=prompt)
        return result.get("response") or None

    def health_check(self) -> Dict:
        return {
            "name": self.name,
            "status": "ok" if self._available else "unavailable",
            "version": self.version,
            "model": self.model,
            "base_url": self.base_url,
        }
