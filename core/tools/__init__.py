"""
MINI-XTAR Tools Package
Provides web search and other tool integrations
"""

from .router import (
    route_prompt,
    ask_with_tools,
    ToolResult,
    AVAILABLE_TOOLS
)

try:
    from .web_search import web_search, web_search_news
    WEB_SEARCH_AVAILABLE = True
except ImportError:
    WEB_SEARCH_AVAILABLE = False
    web_search = None
    web_search_news = None

__all__ = [
    'route_prompt',
    'ask_with_tools',
    'ToolResult',
    'AVAILABLE_TOOLS',
    'web_search',
    'web_search_news',
    'WEB_SEARCH_AVAILABLE'
]