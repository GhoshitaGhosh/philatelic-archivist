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

from duckduckgo_search import DDGS

def search_online_archives(query_text: str) -> dict:
    """Searches the public web for historical stamp information using DuckDuckGo.
    
    Args:
        query_text: The search query (e.g., '1950 Republic of India 2 annas stamp issue date').
        
    Returns:
        A dictionary containing the top search result snippets.
    """
    def _run_search():
        try:
            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(query_text, max_results=3):
                    results.append({
                        "title": r.get("title", ""),
                        "snippet": r.get("body", ""),
                        "url": r.get("href", "")
                    })
            
            if not results:
                return {"result": "No results found on the web."}
                
            return {"result": "Web search successful", "snippets": results}
        except Exception as e:
            return {"error": f"Web search failed: {e}"}

    import concurrent.futures
    # Execute in a pristine thread to prevent DDGS from colliding with FastAPI's active asyncio loop
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_run_search)
        return future.result()
