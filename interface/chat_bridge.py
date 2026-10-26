# interface/chat_bridge.py
"""
Shared ChatBot instance for both avatar and terminal interface.
Ensures consistent conversation memory and tool access.
"""
import threading
from core.chatbot import ChatBot
from core.memory import Memory

# Shared instances
_chatbot = None
_memory = None
_lock = threading.Lock()

# Callbacks for logging
_terminal_log_callback = None
_message_log_callback = None


def get_chatbot(enable_tools: bool = True) -> ChatBot:
    """
    Get or create the shared ChatBot instance.

    Args:
        enable_tools: Whether to enable web search and other tools (default: True)

    Returns:
        Shared ChatBot instance
    """
    global _chatbot, _memory

    with _lock:
        if _chatbot is None:
            print("🤖 Initializing shared ChatBot instance...")

            # Create shared memory
            _memory = Memory()

            # Create chatbot with tool support
            _chatbot = ChatBot(
                model="llama3:latest",
                memory=_memory,
                use_api=True,
                enable_tools=enable_tools,  # Enable web search by default
                system_prompt=(
                    "You are MINI-XTAR, a friendly and helpful AI assistant for Sultan. "
                    "Be concise, helpful, and engaging. When you use web search results, "
                    "cite sources naturally in your response. Always provide accurate, "
                    "up-to-date information when available."
                )
            )

            print("✅ ChatBot ready")
            if enable_tools:
                print("   🔧 Tools enabled: Web Search")

        return _chatbot


def ask_ai(message: str, source: str = "unknown", use_tools: bool = True) -> str:
    """
    Ask the AI assistant a question.

    Args:
        message: User's message
        source: Where the message came from ("avatar", "terminal", etc.)
        use_tools: Whether to use tools for this query (default: True)

    Returns:
        AI's response
    """
    global _terminal_log_callback, _message_log_callback
    
    bot = get_chatbot(enable_tools=use_tools)

    # Log where message came from (terminal callback for avatar only)
    if source == "avatar" and _terminal_log_callback:
        _terminal_log_callback(f"[AVATAR] User: {message}")
    elif source != "unknown":
        print(f"[{source.upper()}] User: {message[:50]}...")

    try:
        # The chatbot will automatically use tools if enabled
        response = bot.ask(message)
        
        # Log response (terminal callback for avatar only)
        if source == "avatar" and _terminal_log_callback:
            _terminal_log_callback(f"[AVATAR] MINI-XTAR: {response}")
        elif source != "unknown":
            print(f"[{source.upper()}] AI: {response[:50]}...")
        
        # Save to chat log via callback (for avatar only - terminal saves in main.py)
        if source == "avatar" and _message_log_callback:
            _message_log_callback("user", message)
            _message_log_callback("assistant", response)
        
        return response
    except Exception as e:
        print(f"❌ Error in ask_ai: {e}")
        import traceback
        traceback.print_exc()
        return "Sorry, I encountered an error processing your request."


def reset_conversation():
    """Clear conversation history (useful for testing)"""
    global _chatbot, _memory

    with _lock:
        if _memory:
            try:
                _memory.clear_history()
                print("🧹 Conversation history cleared")
            except Exception as e:
                print(f"⚠️ Failed to clear history: {e}")


def get_conversation_history(limit: int = 10):
    """Get recent conversation history"""
    bot = get_chatbot()
    try:
        return bot.memory.get_recent_history(limit=limit)
    except Exception as e:
        print(f"⚠️ Failed to get history: {e}")
        return []


# For backward compatibility
def initialize_chatbot(bot=None, terminal_log_callback=None, message_log_callback=None):
    """
    Initialize chat bridge with callbacks.
    
    Args:
        bot: Optional ChatBot instance (if None, will be created automatically)
        terminal_log_callback: Callback to log messages to terminal
        message_log_callback: Callback to save messages to chat log
    """
    global _chatbot, _memory, _terminal_log_callback, _message_log_callback
    
    if bot is not None:
        with _lock:
            _chatbot = bot
            _memory = bot.memory if hasattr(bot, 'memory') else None
    
    if terminal_log_callback:
        _terminal_log_callback = terminal_log_callback
    
    if message_log_callback:
        _message_log_callback = message_log_callback
    
    return get_chatbot()