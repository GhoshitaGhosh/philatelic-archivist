import json
import os

def query_historical_database(query_text: str) -> dict:
    """Queries the local historical registry database for a given era, date, or location.
    
    Args:
        query_text: The search query (e.g., year, location, or series name).
        
    Returns:
        A dictionary containing matching milestone issues.
    """
    db_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'historical_registry.json')
    try:
        with open(db_path, 'r') as f:
            db = json.load(f)
    except Exception as e:
        return {"error": f"Could not load database: {e}"}
        
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
import json

def search_online_archives(query_text: str) -> dict:
    """Searches Wikipedia for historical stamp information and chronological context.
    
    Args:
        query_text: The search query (e.g., '1950 Republic of India stamp').
        
    Returns:
        A dictionary containing the top historical search result snippets.
    """
    try:
        url = "https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch=" + urllib.parse.quote(query_text) + "&utf8=&format=json"
        req = urllib.request.Request(url, headers={'User-Agent': 'PhilatelicArchivist/1.0 (https://github.com/GhoshitaGhosh/philatelic-archivist)'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            
        search_hits = data.get("query", {}).get("search", [])
        results = []
        for r in search_hits[:3]:
            snippet = r.get("snippet", "").replace('<span class="searchmatch">', '').replace('</span>', '').replace('&quot;', '"')
            results.append({
                "title": r.get("title", ""),
                "snippet": snippet,
                "url": f"https://en.wikipedia.org/wiki/{urllib.parse.quote(r.get('title', ''))}"
            })
            
        if not results:
            return {"result": "No results found on Wikipedia."}
            
        return {"result": "Wikipedia search successful", "snippets": results}
    except Exception as e:
        return {"error": f"Web search failed: {e}"}
