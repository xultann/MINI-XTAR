# core/chatbot.py
import requests
import subprocess
import json
import traceback
from datetime import datetime
from typing import Optional

from core.memory import Memory


class ChatBot:
    """
    ChatBot wrapper that uses either an Ollama HTTP API (preferred) or falls
    back to running `ollama run <model>` as a subprocess for offline use.

    - Saves conversation to Memory via memory.save_message(...)
    - Builds context from memory.get_recent_history(...)
    - Supports tool integration (web search, etc.)
    """

    def __init__(
            self,
            model: str = "llama3:latest",
            memory: Optional[Memory] = None,
            use_api: bool = True,
            base_url: str = "http://localhost:11434",
            system_prompt: Optional[str] = None,
            enable_tools: bool = False,
    ):
        self.model = model
        self.memory = memory or Memory()
        self.use_api = use_api
        self.base_url = base_url.rstrip("/")
        self.api_url = f"{self.base_url}/api/generate"
        self._mode_logged = False

        # Tool support
        self.enable_tools = enable_tools

        # Try to import tool router if tools are enabled
        if self.enable_tools:
            try:
                from core.tools.router import route_prompt
                self.route_prompt = route_prompt
                print("✅ Tool system enabled")
            except ImportError:
                print("⚠️ Tool system not available. Create core/tools/ folder.")
                self.enable_tools = False
                self.route_prompt = None
        else:
            self.route_prompt = None

        # Default system prompt
        if system_prompt is not None:
            self.system_prompt = system_prompt
        else:
            self.system_prompt = (
                "You are MINI-XTAR, a friendly and helpful assistant for Sultan. "
                "Be concise and helpful. Use the available memories when relevant. "
                "When provided with web search results, incorporate them naturally into your response."
            )

    # -----------------------
    # Utility: check Ollama API
    # -----------------------
    def _is_ollama_running(self) -> bool:
        """Quick check whether the Ollama HTTP API is reachable."""
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=2)
            return r.status_code == 200
        except Exception:
            return False

    def _detect_api_endpoint(self):
        """
        Some Ollama versions use /api/chat instead of /api/generate.
        Probe and adjust if we get a 404.
        """
        try:
            test_payload = {"model": self.model, "prompt": "ping", "stream": False}
            resp = requests.post(self.api_url, json=test_payload, timeout=4)
            if resp.status_code == 404:
                self.api_url = f"{self.base_url}/api/chat"
        except Exception:
            pass

    # -----------------------
    # Offline runner
    # -----------------------
    def _run_offline(self, text: str) -> str:
        """
        Call `ollama run <model>` as a subprocess and return stdout.
        """
        try:
            proc = subprocess.run(
                ["ollama", "run", self.model],
                input=text,
                text=True,
                capture_output=True,
                timeout=120,
            )
            out = proc.stdout.strip()
            if out:
                return out
            if proc.stderr:
                return f"(offline) No output. stderr: {proc.stderr.strip()}"
            return "No response (offline)."
        except Exception as e:
            traceback.print_exc()
            return f"Offline generation failed: {e}"

    # -----------------------
    # Main ask() - WITH TOOL SUPPORT
    # -----------------------
    def ask(self, text: str, tool_context: Optional[str] = None) -> str:
        """
        Ask the model a question with optional tool support.

        Args:
            text: user message
            tool_context: optional context from tools (web search results, etc.)

        Returns:
            assistant reply (string)
        """
        # 1) Save user message to memory
        try:
            self.memory.save_message("user", text)
        except Exception:
            print("[WARN] memory.save_message failed")
            traceback.print_exc()

        # 2) Check if tools should be used (only if no tool_context already provided)
        if self.enable_tools and tool_context is None and self.route_prompt:
            try:
                routed = self.route_prompt(text, enable_tools=True)
                if routed.used_tool:
                    print(f"🔧 Tool used: {routed.tool_name}")
                    tool_context = routed.tool_output
            except Exception as e:
                print(f"⚠️ Tool routing failed: {e}")
                traceback.print_exc()

        # 3) Build messages/context
        past_messages = []
        try:
            past_messages = self.memory.get_recent_history(limit=6)
        except Exception:
            past_messages = []

        # Get relevant memories (core + semantic)
        relevant_memories = ""
        try:
            relevant_memories = self.memory.recall_relevant(text, limit=5)
        except Exception:
            pass

        # Build prompt
        now_str = datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
        prompt_parts = [
            f"System: {self.system_prompt}",
            f"Current time: {now_str}",
        ]
        
        # Add core memory and relevant memories
        if relevant_memories:
            prompt_parts.append("Relevant memories:")
            prompt_parts.append(relevant_memories)
            prompt_parts.append("")  # Empty line separator

        if past_messages:
            prompt_parts.append("Recent conversation:")
            for m in past_messages:
                role = m.get("role", "user")
                content = m.get("content", "")
                prompt_parts.append(f"{role}: {content}")

        if tool_context:
            prompt_parts.append(f"\n{tool_context}\n")

        prompt_parts.append(f"user: {text}")
        prompt_parts.append("assistant:")

        combined_input = "\n".join(prompt_parts)

        # 4) Try online mode (Ollama HTTP API)
        reply = None
        if self.use_api and self._is_ollama_running():
            if not self._mode_logged:
                print("[MODE] Connected to Ollama API (online mode).")
                self._mode_logged = True

            self._detect_api_endpoint()

            try:
                payload = {"model": self.model, "prompt": combined_input, "stream": False}
                resp = requests.post(self.api_url, json=payload, timeout=120)
                resp.raise_for_status()
                data = resp.json()

                # Extract reply
                if isinstance(data, dict):
                    reply = data.get("response")
                    if not reply:
                        msg = data.get("message")
                        if isinstance(msg, dict):
                            reply = msg.get("content", "")
                        elif isinstance(msg, str):
                            reply = msg
                    if not reply:
                        for k in ("output", "text", "result"):
                            if k in data:
                                reply = data[k]
                                break

                if not reply:
                    reply = json.dumps(data)

            except Exception as e:
                print(f"[WARN] Online mode failed ({e}). Falling back to offline.")
                traceback.print_exc()
                reply = None

        # 5) Offline fallback
        if reply is None:
            if not self._mode_logged:
                print("[MODE] Running in offline mode (subprocess).")
                self._mode_logged = True
            reply = self._run_offline(combined_input)

        # 6) Save assistant reply to memory
        try:
            self.memory.save_message("assistant", reply)
        except Exception:
            print("[WARN] memory.save_message failed when saving assistant reply")
            traceback.print_exc()

        return reply

    def ask_with_tool_context(self, user_message: str, tool_context: str) -> str:
        """Convenience wrapper to explicitly pass tool_context."""
        return self.ask(user_message, tool_context=tool_context)