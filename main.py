import threading
import time
import os
import json
from datetime import datetime
from core.memory import Memory
from interface.avatar import MiniAvatar
from core.chatbot import ChatBot
from interface.chat_bridge import initialize_chatbot, ask_ai

def terminal_logger(msg):
    print(msg)

def message_logger(role, text):
    print(f"[{role.upper()}] {text}")

def show_thinking(stop_event):
    symbols = ["|", "/", "-", "\\"]
    i = 0
    while not stop_event.is_set():
        print(f"\rMINI-XTAR: Thinking... {symbols[i % len(symbols)]}", end="", flush=True)
        i += 1
        time.sleep(0.2)
    print("\r", end="", flush=True)

def save_chat_log(session_id, messages):
    date_str = datetime.now().strftime("%Y-%m-%d")
    folder = "data/chat_logs"
    os.makedirs(folder, exist_ok=True)
    file_path = os.path.join(folder, f"{date_str}_session_{session_id}.json")

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump({
            "session_id": session_id,
            "date": date_str,
            "messages": messages
        }, f, indent=4, ensure_ascii=False)

# Global messages list to track all conversations
_messages = []

def terminal_log_callback(message):
    """Callback to log avatar interactions to terminal (non-blocking)"""
    # Use sys.stdout directly to avoid interfering with input()
    import sys
    sys.stdout.write(f"\n{message}\n")
    sys.stdout.flush()

def message_log_callback(role, content):
    """Callback to save avatar messages to chat log"""
    global _messages
    _messages.append({"role": role, "content": content})

def run_avatar(bot, shutdown_event):
    """Run avatar with shared chatbot instance"""
    avatar = MiniAvatar(chatbot=bot, shutdown_event=shutdown_event)
    avatar.run()

def main():
    print("🤖 MINI-XTAR is online!")
    memory = Memory()

    if not memory.memory_data["core"]:
        print("Loading core memories for the first time...")
        memory.add_core_memory(
            "You are MINI-XTAR, also called Mini. You are a cool, confident, and helpful AI assistant "
            "created by your user, Sultan (nicknames: XTAR, XNAKE). You are their friend and digital partner. "
            "Your personality is friendly, energetic, and supportive. You refer to yourself as MINI-XTAR, "
            "not 'I' when introducing yourself, but you may use 'I' casually in conversation. "
            "You and Sultan share the color violet and love creating projects together."
        )
        memory.add_core_memory(
            "Your user, Sultan, is the only person you talk with. They are your creator and best friend. "
            "Every time you're interacting, Sultan is the user you assist. "
            "Sultan is a software engineer graduate with many creative hobbies "
            "like making music, games, stories, art, and animations. "
            "You exist to assist Sultan in their projects and share their creative vision. "
            "Always remember that Sultan is the one and only user of your AI, "
            "and refer to them directly as 'you'."
        )

    # --- Create shared chatbot instance ---
    bot = ChatBot(
        model="llama3:latest",
        memory=memory,
        use_api=True,
        enable_tools=True  # Enable router + web search
    )
    
    # --- Session setup ---
    session_id = len(os.listdir("data/chat_logs")) + 1 if os.path.exists("data/chat_logs") else 1
    global _messages
    _messages = []
    shutdown_event = threading.Event()

    # --- Initialize chat bridge with shared chatbot and callbacks ---
    initialize_chatbot(bot,
                     terminal_log_callback=terminal_log_callback,
                     message_log_callback=message_log_callback)
    print("[SYSTEM] Avatar connected to shared chatbot instance (memory synchronized)")

    # --- Launch avatar in a separate thread with shared bot ---
    avatar_thread = threading.Thread(target=run_avatar, args=(bot, shutdown_event), daemon=True)
    avatar_thread.start()
    print("[SYSTEM] Avatar window launched")

    # --- Terminal chat loop ---
    try:
        while not shutdown_event.is_set():
            user_input = input("\nYou: ").strip()
            if user_input.lower() in ["exit", "quit"]:
                break

            # Start thinking animation
            stop_event = threading.Event()
            spinner_thread = threading.Thread(target=show_thinking, args=(stop_event,))
            spinner_thread.start()

            # Get response (via router + tools)
            response = ask_ai(user_input, source="terminal", use_tools=True)

            # Stop spinner
            stop_event.set()
            spinner_thread.join()

            print(f"MINI-XTAR: {response}")
            _messages.append({"role": "user", "content": user_input})
            _messages.append({"role": "assistant", "content": response})
    except KeyboardInterrupt:
        pass
    finally:
        print("Shutting down MINI-XTAR...")
        save_chat_log(session_id, _messages)

if __name__ == "__main__":
    main()
