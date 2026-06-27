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


