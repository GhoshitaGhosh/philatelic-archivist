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
import json
import asyncio
import re

async def search_online_archives(query_texts: list[str]) -> dict:
    """Searches the public web for historical stamp information using parallel Wikipedia API searches.
    
    Args:
        query_texts: An array of distinct search queries (e.g., ['1950 Republic of India stamp', 'India Republic stamp 1950 denomination']).
        
    Returns:
        A dictionary containing aggregated historical search result snippets across all queries.
    """
    def _run_single_search(query_text: str):
        # Use generator=search with prop=extracts to fetch rich, full introductory paragraphs instead of truncated HTML snippets
        url = "https://en.wikipedia.org/w/api.php?action=query&generator=search&gsrsearch=" + urllib.parse.quote(query_text) + "&prop=extracts&exsentences=5&exintro=1&explaintext=1&utf8=&format=json"
        req = urllib.request.Request(url, headers={'User-Agent': 'PhilatelicArchivist/1.0'})
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                
            results = []
            pages = data.get('query', {}).get('pages', {})
            for page_id, page_data in list(pages.items())[:3]:
                # Extract full plain-text sentences which are highly likely to contain exact historical dates
                extract = page_data.get('extract', '').strip()
                if extract:
                    results.append(extract)
            return {"query": query_text, "rich_extracts": results}
        except Exception as e:
            return {"query": query_text, "error": str(e)}

    try:
        if isinstance(query_texts, str):
            query_texts = [query_texts]
            
        # Offload blocking HTTP requests to a background thread pool and execute in parallel
        tasks = [asyncio.to_thread(_run_single_search, query) for query in query_texts]
        results = await asyncio.gather(*tasks)
        return {"result": "Parallel Wikipedia search successful", "data": results}
    except Exception as e:
        return {"error": f"Parallel Wikipedia search failed: {e}"}
