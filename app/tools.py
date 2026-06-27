import json
import os

_db_cache = None

def query_historical_database(query_text: str) -> dict:
    """Queries the local historical registry database for a given era, date, or location.
    
    Args:
        query_text: The search query (e.g., year, location, or series name).
        
    Returns:
        A dictionary containing matching milestone issues.
    """
    global _db_cache
    if _db_cache is None:
        db_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'historical_registry.json')
        try:
            with open(db_path, 'r') as f:
                _db_cache = json.load(f)
        except Exception as e:
            return {"error": f"Could not load database: {e}"}
            
    db = _db_cache
        
    results = []
    for issue in db.get("milestone_issues", []):
        search_target = f"{issue.get('issue_year', '')} {issue.get('series', '')} " \
                        f"{' '.join(issue.get('primary_locations', []))} {issue.get('launch_date', '')}".lower()
        if query_text.lower() in search_target:
            results.append(issue)
            
    if not results:
        return {"result": f"No exact matching milestone found for '{query_text}'. Checking general records."}
        
    return {"result": "Matches found", "milestones": results}

import urllib.request
import urllib.parse
import re
import asyncio

async def search_online_archives(query_text: str) -> dict:
    """Searches the public web for historical stamp information using DuckDuckGo.
    
    Args:
        query_text: The search query (e.g., '1950 Republic of India stamp').
        
    Returns:
        A dictionary containing the top historical search result snippets.
    """
    def _run_search():
        url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query_text)
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode('utf-8')
            
        snippets = re.findall(r'<a class="result__snippet[^>]*>(.*?)</a>', html, re.IGNORECASE | re.DOTALL)
        if not snippets:
            return {"result": "No results found on the web."}
            
        results = []
        for s in snippets[:3]:
            # Clean HTML tags and decode basic entities
            clean_s = re.sub(r'<[^>]+>', '', s).strip()
            clean_s = clean_s.replace('&#39;', "'").replace('&quot;', '"').replace('&amp;', '&')
            results.append({"snippet": clean_s})
            
        return {"result": "Web search successful", "snippets": results}

    try:
        # Offload the blocking HTTP request to a background thread to prevent starving the FastAPI event loop
        return await asyncio.to_thread(_run_search)
    except Exception as e:
        return {"error": f"Web search failed: {e}"}
