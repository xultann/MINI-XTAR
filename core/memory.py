import json
import os
import numpy as np
import torch
from datetime import datetime
from sentence_transformers import SentenceTransformer, util


class Memory:
    def __init__(self, memory_file="data/memory/memory.json"):
        self.memory_file = memory_file

        # === Chat history for LLM ===
        self.history = []  # <<< FIX: required for chatbot.py

        # === Embedding memory clusters ===
        self.memory_data = {"core": [], "short_term": [], "long_term": []}

        # --- Local model path ---
        local_model_path = "models/all-MiniLM-L6-v2"

        # --- Try to load embedding model ---
        if os.path.exists(local_model_path):
            print(f"[MEMORY] Loading local embedding model from: {local_model_path}")
            self.model = SentenceTransformer(local_model_path)
        else:
            print("[MEMORY] Local model not found, downloading...")
            try:
                self.model = SentenceTransformer("all-MiniLM-L6-v2")
                os.makedirs("models", exist_ok=True)
                self.model.save(local_model_path)
            except Exception as e:
                print(f"[ERROR] Could not load embedding model: {e}")
                self.model = None

        # Load JSON memory (core/short/long-term)
        self._load_memory()
        
        # If memory.json was missing or core memory is empty, try to restore from chat logs
        memory_missing = not os.path.exists(self.memory_file)
        core_empty = not self.memory_data["core"]
        
        if memory_missing:
            print("[MEMORY] memory.json not found, attempting to restore from chat logs...")
            self._restore_from_chat_logs()
        elif core_empty:
            print("[MEMORY] Core memory is empty, will be initialized with defaults.")

    # ==========================
    # Load embedded memory (NO chat history - that goes to chat_logs)
    # ==========================
    def _load_memory(self):
        if os.path.exists(self.memory_file):
            with open(self.memory_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.memory_data = data.get("memory_data", self.memory_data)
                # Chat history is NOT loaded from memory.json - it's runtime only
                # Chat logs are saved separately in data/chat_logs/
        # History is always empty on startup (runtime-only for LLM context)
        self.history = []

    def _save_memory(self):
        """Save only semantic memories (core, short_term, long_term) - NOT chat history"""
        os.makedirs(os.path.dirname(self.memory_file), exist_ok=True)
        with open(self.memory_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "memory_data": self.memory_data
                    # chat_history is NOT saved here - it goes to chat_logs/ via callbacks
                },
                f,
                indent=4
            )

    # ==========================
    # Embedding utilities
    # ==========================
    def _embed(self, text):
        if self.model is None:
            return np.zeros(384).tolist()
        return self.model.encode(text).tolist()

    # ==========================
    # Core Memory (Permanent)
    # ==========================
    def add_core_memory(self, content):
        entry = {
            "role": "system",
            "content": content,
            "embedding": self._embed(content),
            "strength": 10.0,
            "timestamp": datetime.now().isoformat()
        }

        if content not in [m["content"] for m in self.memory_data["core"]]:
            self.memory_data["core"].append(entry)
            self._save_memory()

    # ==========================
    # Save Message (Dual System)
    # ==========================
    def save_message(self, role, content, importance=1.0):
        """Store message for LLM context + store in semantic memory."""

        # --- For LLM chat context ---
        self.history.append({"role": role, "content": content})
        self.history = self.history[-50:]  # avoid infinite growth

        # --- For semantic memory (embeddings) ---
        vector = self._embed(content)
        entry = {
            "role": role,
            "content": content,
            "embedding": vector,
            "strength": importance,
            "timestamp": datetime.now().isoformat()
        }
        self.memory_data["short_term"].append(entry)

        # Move older ST memories to LT
        if len(self.memory_data["short_term"]) > 10:
            self.memory_data["long_term"].extend(self.memory_data["short_term"][:-5])
            self.memory_data["short_term"] = self.memory_data["short_term"][-5:]

        self._apply_decay()
        self._save_memory()

    # ==========================
    # Decay long-term memory
    # ==========================
    def _apply_decay(self):
        updated = []
        for m in self.memory_data["long_term"]:
            m["strength"] = max(0, m.get("strength", 1.0) * 0.98)
            if m["strength"] > 0.3:
                updated.append(m)
        self.memory_data["long_term"] = updated

    # ==========================
    # Semantic recall
    # ==========================
    def recall_relevant(self, query, limit=5):
        all_m = (
                self.memory_data["core"]
                + self.memory_data["long_term"]
                + self.memory_data["short_term"]
        )
        if not all_m or self.model is None:
            return ""

        query_vec = self.model.encode(query)
        scored = []

        for m in all_m:
            q = torch.tensor(query_vec, dtype=torch.float32)
            v = torch.tensor(m["embedding"], dtype=torch.float32)
            sim = util.cos_sim(q, v).item()
            score = sim * m.get("strength", 1.0)
            scored.append((score, m))

        scored.sort(reverse=True, key=lambda x: x[0])
        top = scored[:limit]
        return "\n".join(f"{m['role']}: {m['content']}" for _, m in top)

    # ==========================
    # Chat history for LLM
    # ==========================
    def get_recent_history(self, limit=6):
        return self.history[-limit:]
    
    # ==========================
    # Restore from chat logs
    # ==========================
    def _restore_from_chat_logs(self):
        """Restore memory from chat logs when memory.json is missing or empty."""
        chat_logs_dir = "data/chat_logs"
        if not os.path.exists(chat_logs_dir):
            print("[MEMORY] No chat logs directory found, skipping restoration.")
            return
        
        # Get all chat log files, sorted by modification time (newest first)
        log_files = []
        for filename in os.listdir(chat_logs_dir):
            if filename.endswith(".json"):
                filepath = os.path.join(chat_logs_dir, filename)
                log_files.append((os.path.getmtime(filepath), filepath))
        
        if not log_files:
            print("[MEMORY] No chat log files found, skipping restoration.")
            return
        
        # Sort by modification time (newest first)
        log_files.sort(reverse=True)
        
        print(f"[MEMORY] Found {len(log_files)} chat log files, restoring from most recent...")
        
        # Restore core memory if missing
        if not self.memory_data["core"]:
            # Core memory should be restored from the system - add default core memories
            # These will be added in main.py if needed, but we can also extract from chat logs
            print("[MEMORY] Core memory empty, will be initialized with defaults.")
        
        # Load recent chat history from the most recent chat logs
        # Process logs in reverse chronological order (newest first)
        # Collect messages from newest files first, taking newest messages from each file
        restored_messages = []
        max_messages_to_restore = 50  # Restore up to 50 recent messages
        
        for _, filepath in log_files:
            if len(restored_messages) >= max_messages_to_restore:
                break
            
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    log_data = json.load(f)
                    messages = log_data.get("messages", [])
                    
                    # Take messages from this file in reverse order (newest first)
                    # Prepend to our list so newest messages are at the front
                    for msg in reversed(messages):
                        if len(restored_messages) >= max_messages_to_restore:
                            break
                        restored_messages.insert(0, msg)
            except Exception as e:
                print(f"[MEMORY] Warning: Could not load chat log {filepath}: {e}")
                continue
        
        # Restore chat history (in chronological order - oldest to newest)
        # restored_messages is currently newest-first, so reverse it
        if restored_messages:
            restored_messages.reverse()  # Now oldest to newest
            self.history = restored_messages  # Take all restored messages (up to max)
            print(f"[MEMORY] Restored {len(self.history)} messages from chat logs.")
            
            # Also add important messages to semantic memory
            # Extract key information from conversations
            # Use the last 20 messages (most recent) for semantic memory
            for msg in self.history[-20:]:  # Last 20 messages (most recent)
                role = msg.get("role", "")
                content = msg.get("content", "")
                
                # Add to semantic memory if it contains important information
                # (like user name, preferences, etc.)
                if role == "user" and content:
                    # Check if message contains name or important info
                    content_lower = content.lower()
                    if any(keyword in content_lower for keyword in ["i am", "my name is", "i'm", "call me"]):
                        # This might contain user identity info
                        importance = 2.0
                    else:
                        importance = 0.5
                    
                    # Add to short-term memory
                    vector = self._embed(content)
                    entry = {
                        "role": role,
                        "content": content,
                        "embedding": vector,
                        "strength": importance,
                        "timestamp": datetime.now().isoformat()
                    }
                    self.memory_data["short_term"].append(entry)
            
            # Limit short-term memory size
            if len(self.memory_data["short_term"]) > 20:
                self.memory_data["long_term"].extend(self.memory_data["short_term"][:-10])
                self.memory_data["short_term"] = self.memory_data["short_term"][-10:]
            
            # Save restored memory
            self._save_memory()
            print("[MEMORY] Memory restored and saved successfully.")
        else:
            print("[MEMORY] No messages found in chat logs to restore.")
