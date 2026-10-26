"""
Web Search Tool for MINI-XTAR
Uses DuckDuckGo with optimized query formatting
"""
from typing import Dict, List, Optional
import re

try:
    from duckduckgo_search import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    DDGS_AVAILABLE = False
    print("⚠️ duckduckgo-search not installed. Run: pip install duckduckgo-search")


def optimize_search_query(query: str) -> str:
    """
    Optimize query for better DuckDuckGo results.
    Converts conversational queries to better search terms.
    """
    query = query.strip()

    # Remove common conversational prefixes
    conversational_prefixes = [
        "search for ",
        "find ",
        "look up ",
        "show me ",
        "tell me about ",
        "what is ",
        "what are ",
        "who is ",
        "where is ",
        "when is ",
        "how to ",
        "can you find ",
        "i want to know about ",
    ]

    query_lower = query.lower()
    for prefix in conversational_prefixes:
        if query_lower.startswith(prefix):
            query = query[len(prefix):]
            break

    # For "best X in Y" queries, add context words
    if re.search(r'\bbest\b.*\bin\b', query, re.IGNORECASE):
        # Add "top" and "popular" to help search engines understand
        if "dish" in query.lower() or "food" in query.lower():
            query = f"top popular {query} cuisine restaurant"
        elif "place" in query.lower():
            query = f"top tourist {query} travel guide"

    # For questions, convert to declarative
    question_conversions = {
        r'^what is the (.+)': r'\1 definition',
        r'^who is (.+)': r'\1 biography',
        r'^where is (.+)': r'\1 location',
        r'^when is (.+)': r'\1 date time',
    }

    for pattern, replacement in question_conversions.items():
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            query = re.sub(pattern, replacement, query, flags=re.IGNORECASE)
            break

    return query.strip()


def web_search(query: str, max_results: int = 5, region: str = "wt-wt") -> Dict:
    """
    Search the web using DuckDuckGo with optimized queries.

    Args:
        query: Search query string
        max_results: Maximum number of results to return
        region: Region code (default: wt-wt for worldwide)

    Returns:
        Dictionary with:
        - success: bool
        - results: List of search results
        - query: Original query
        - optimized_query: The query actually used for search
        - error: Error message (if failed)
    """

    if not DDGS_AVAILABLE:
        return {
            "success": False,
            "results": [],
            "query": query,
            "optimized_query": query,
            "error": "DuckDuckGo search not available. Install: pip install duckduckgo-search"
        }

    try:
        # Optimize the query for better results
        optimized_query = optimize_search_query(query)
        print(f"🔍 Original query: {query}")
        print(f"🔍 Optimized query: {optimized_query}")

        # Initialize DuckDuckGo search
        with DDGS() as ddgs:
            results = []

            # Try optimized query first
            try:
                search_results = list(ddgs.text(
                    keywords=optimized_query,
                    region=region,
                    safesearch="moderate",
                    timelimit=None,
                    max_results=max_results * 2  # Get extra to filter
                ))
            except Exception as e:
                print(f"   ⚠️ Optimized search failed: {e}")
                # Fallback to original query
                search_results = list(ddgs.text(
                    keywords=query,
                    region=region,
                    safesearch="moderate",
                    timelimit=None,
                    max_results=max_results * 2
                ))

            # Process and filter results
            seen_urls = set()
            for r in search_results:
                title = r.get("title", "")
                url = r.get("href", "")
                snippet = r.get("body", "")

                # Skip empty results
                if not title or not snippet or not url:
                    continue

                # Skip duplicates
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                # Filter out low-quality results
                # Skip if it's a help/support page (unless query is about help)
                if "help" not in query.lower() and "support" not in query.lower():
                    if any(x in url.lower() for x in ["/help", "/support", "/faq"]):
                        continue

                # Skip grammar/language learning sites for non-language queries
                if not any(word in query.lower() for word in ["grammar", "language", "english", "word"]):
                    if any(x in url.lower() for x in ["stackexchange.com/questions", "baidu.com", "zhihu.com"]):
                        # Unless it's about the actual topic
                        if not any(keyword in title.lower() + snippet.lower()
                                 for keyword in query.lower().split()[:3]):
                            continue

                results.append({
                    "title": title,
                    "url": url,
                    "snippet": snippet,
                })

                # Stop if we have enough good results
                if len(results) >= max_results:
                    break

            # If filtering removed too many results, try again with less strict filters
            if len(results) < 2 and len(search_results) > 0:
                print("   ⚠️ Too few quality results, relaxing filters...")
                results = []
                for r in search_results[:max_results]:
                    results.append({
                        "title": r.get("title", ""),
                        "url": r.get("href", ""),
                        "snippet": r.get("body", ""),
                    })

            print(f"   ✅ Found {len(results)} quality results")

            return {
                "success": True,
                "results": results,
                "query": query,
                "optimized_query": optimized_query,
                "error": None
            }

    except Exception as e:
        print(f"   ❌ Search failed: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "results": [],
            "query": query,
            "optimized_query": query,
            "error": str(e)
        }


def web_search_news(query: str, max_results: int = 5) -> Dict:
    """
    Search for news articles using DuckDuckGo News.

    Args:
        query: Search query
        max_results: Max news articles to return

    Returns:
        Same format as web_search()
    """

    if not DDGS_AVAILABLE:
        return {
            "success": False,
            "results": [],
            "query": query,
            "error": "DuckDuckGo search not available"
        }

    try:
        # Optimize query for news
        optimized_query = optimize_search_query(query)
        print(f"📰 Searching news: {query}")
        if optimized_query != query:
            print(f"📰 Optimized: {optimized_query}")

        with DDGS() as ddgs:
            results = []
            news_results = ddgs.news(
                keywords=optimized_query,
                max_results=max_results
            )

            for r in news_results:
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("body", ""),
                    "date": r.get("date", ""),
                    "source": r.get("source", "")
                })

            print(f"   ✅ Found {len(results)} news articles")

            return {
                "success": True,
                "results": results,
                "query": query,
                "optimized_query": optimized_query,
                "error": None
            }

    except Exception as e:
        print(f"   ❌ News search failed: {e}")
        return {
            "success": False,
            "results": [],
            "query": query,
            "error": str(e)
        }


# Test
if __name__ == "__main__":
    print("=== Web Search Test ===\n")

    test_queries = [
        "best dish in Japan",
        "search for places to visit in Malaysia",
        "what is machine learning",
    ]

    for q in test_queries:
        print(f"\nTesting: {q}")
        result = web_search(q, max_results=3)
        if result["success"]:
            print(f"✅ Got {len(result['results'])} results")
            for i, r in enumerate(result["results"], 1):
                print(f"  {i}. {r['title'][:60]}...")
        else:
            print(f"❌ Failed: {result['error']}")