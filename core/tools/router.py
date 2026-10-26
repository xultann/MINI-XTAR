"""
Tool Router for MINI-XTAR
Handles web search and other tool integrations
"""
from typing import Optional, List, Dict
import json

# Try to import web_search (will create this next)
try:
    from core.tools.web_search import web_search

    WEB_SEARCH_AVAILABLE = True
except ImportError:
    print("⚠️ Web search not available. Install: pip install duckduckgo-search")
    WEB_SEARCH_AVAILABLE = False


class ToolResult:
    """Container for tool execution results"""

    def __init__(self,
                 used_tool: bool,
                 tool_name: Optional[str],
                 tool_output: str,
                 final_prompt: str,
                 metadata: Optional[Dict] = None):
        self.used_tool = used_tool
        self.tool_name = tool_name
        self.tool_output = tool_output
        self.final_prompt = final_prompt
        self.metadata = metadata or {}


def _needs_web_search(prompt: str) -> bool:
    """
    Heuristic to detect if web search is needed.
    Returns True if user is asking for current/online information.
    """
    p = prompt.lower()

    # Explicit search requests
    search_keywords = [
        "search for", "look up", "find information", "google",
        "what is the latest", "current", "today", "news about",
        "recent", "update on", "happening now", "right now",
        "this year", "this month", "this week",
        "weather", "stock price", "score", "results"
    ]

    # Questions that often need current info
    question_patterns = [
        "who is the current", "what is the price of",
        "when is the next", "where is", "how much does",
        "is there a", "are there any"
    ]

    # Explicit "don't use internet" override
    if any(x in p for x in ["offline only", "no internet", "don't search", "without searching"]):
        return False

    # Check for search keywords
    if any(keyword in p for keyword in search_keywords):
        return True

    # Check for question patterns
    if any(pattern in p for pattern in question_patterns):
        return True

    return False


def _extract_search_query(prompt: str) -> str:
    """
    Extract the actual search query from user prompt.
    Clean up conversational fluff.
    """
    # Remove common prefixes
    cleaned = prompt
    prefixes_to_remove = [
        "can you search for",
        "please search for",
        "search for",
        "look up",
        "find information about",
        "google",
        "tell me about",
        "what is",
        "who is",
    ]

    for prefix in prefixes_to_remove:
        if cleaned.lower().startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()
            break

    # Remove question marks and clean up
    cleaned = cleaned.rstrip("?").strip()

    return cleaned if cleaned else prompt


def route_prompt(prompt: str, enable_tools: bool = True) -> ToolResult:
    """
    Route user prompt to appropriate tools.

    Args:
        prompt: User's message
        enable_tools: Whether tools are enabled (can be disabled for testing)

    Returns:
        ToolResult with tool output and formatted prompt
    """

    # If tools disabled, return raw prompt
    if not enable_tools:
        return ToolResult(
            used_tool=False,
            tool_name=None,
            tool_output="",
            final_prompt=prompt
        )

    # Check if web search is needed
    if WEB_SEARCH_AVAILABLE and _needs_web_search(prompt):
        print("🔍 Web search triggered")

        # Extract clean query
        query = _extract_search_query(prompt)
        print(f"   Query: {query}")

        try:
            # Perform web search
            search_results = web_search(query, max_results=5)

            if search_results and search_results.get("results"):
                # Format search results for context
                results_text = "Web Search Results:\n\n"
                for i, result in enumerate(search_results["results"], 1):
                    title = result.get("title", "No title")
                    snippet = result.get("snippet", "No description")
                    url = result.get("url", "")
                    results_text += f"{i}. {title}\n   {snippet}\n   Source: {url}\n\n"

                # Build enhanced prompt with search context
                tool_context = (
                    "You have access to current web search results.\n"
                    "Use this information to provide an accurate, up-to-date answer.\n\n"
                    f"{results_text}\n"
                    "Based on the above search results, answer the user's question.\n"
                )

                final_prompt = f"{tool_context}\nUser: {prompt}\nAssistant:"

                return ToolResult(
                    used_tool=True,
                    tool_name="web_search",
                    tool_output=results_text,
                    final_prompt=final_prompt,
                    metadata={
                        "query": query,
                        "num_results": len(search_results["results"]),
                        "search_engine": "DuckDuckGo"
                    }
                )
            else:
                print("   ⚠️ No search results found")

        except Exception as e:
            print(f"   ❌ Web search failed: {e}")

    # No tools used - return standard prompt
    return ToolResult(
        used_tool=False,
        tool_name=None,
        tool_output="",
        final_prompt=prompt
    )


def ask_with_tools(bot, prompt: str) -> str:
    """
    Convenience function to ask bot with automatic tool routing.

    Args:
        bot: ChatBot instance
        prompt: User message

    Returns:
        Bot response (string)
    """
    # Route to appropriate tools
    routed = route_prompt(prompt, enable_tools=bot.enable_tools)

    # If no tools were used, do normal ask
    if not routed.used_tool:
        return bot.ask(prompt)

    # Tools were used - pass tool output as context
    print(f"✅ Using tool: {routed.tool_name}")
    return bot.ask(prompt, tool_context=routed.tool_output)


# Available tools definition for future OpenAI-style tool calling
AVAILABLE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for current, real-time information. Use this when the user asks about recent events, current prices, weather, news, or anything requiring up-to-date information.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to look up"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 5)",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        }
    }
]