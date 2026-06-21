import os
import pathlib

# Manually load .env variables using an absolute path to ensure the Gemini API key 
# is injected regardless of the execution working directory.
env_path = pathlib.Path(__file__).parent.parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            if line.strip() and not line.startswith("#"):
                key, val = line.strip().split("=", 1)
                os.environ[key.strip()] = val.strip()

import asyncio
import json
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from google.adk.runners import InMemoryRunner
from google.genai import types

from app.agent import app as adk_app

app = FastAPI(title="Philatelic Archivist API")

# Setup CORS for local UI development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize the ADK InMemoryRunner to wrap the workflow
runner = InMemoryRunner(app=adk_app)

# Global lock for secure single-tenant BYOK execution
api_key_lock = asyncio.Lock()

@app.get("/api/config")
async def get_config():
    """Checks if the server is already authenticated."""
    has_key = bool(os.environ.get("GEMINI_API_KEY"))
    has_gcp = bool(os.environ.get("GOOGLE_CLOUD_PROJECT"))
    from fastapi.responses import JSONResponse
    return JSONResponse({"requires_key": not (has_key or has_gcp)})

@app.post("/api/archive")
async def archive_endpoint(request: Request):
    """Endpoint that accepts a philatelic description and streams ADK node events back."""
    data = await request.json()
    user_input = data.get("input", "")
    image_b64 = data.get("image", None)
    mime_type = data.get("mime_type", "image/jpeg")
    x_gemini_key = request.headers.get("X-Gemini-Key", None)
    
    async def event_stream():
        requires_key = not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_CLOUD_PROJECT"))
        if requires_key and not x_gemini_key:
            yield json.dumps({"type": "event", "route": "flagged", "output": "Server requires a Gemini API Key. Please provide it in the UI."}) + "\n"
            return
            
        lock_acquired = False
        if requires_key and x_gemini_key:
            await api_key_lock.acquire()
            lock_acquired = True
            os.environ["GEMINI_API_KEY"] = x_gemini_key
            
        try:
            # Create a session for the local dev execution
            session = await runner.session_service.create_session(
            app_name="app", user_id="local_ui"
        )
        
            parts = []
            if image_b64:
                import base64
                try:
                    image_bytes = base64.b64decode(image_b64)
                    parts.append(types.Part.from_bytes(data=image_bytes, mime_type=mime_type))
                except Exception as e:
                    print(f"Error decoding image: {e}")
                    
            if user_input:
                parts.append(types.Part.from_text(text=user_input))
                
            msg = types.Content(role="user", parts=parts)
            
            # Dynamically set the model based on user selection
            model_name = data.get("model", "gemini-3.1-flash-lite")
            from app.agent import visual_ocr_node, chronological_context_node, archival_synthesis_node
            visual_ocr_node.model = model_name
            chronological_context_node.model = model_name
            archival_synthesis_node.model = model_name
            
            # Iterate over the graph workflow event stream
            async for event in runner.run_async(
                user_id="local_ui",
                session_id=session.id,
                new_message=msg,
            ):
                output_data = event.output
                if hasattr(output_data, "model_dump"):
                    output_data = output_data.model_dump()
                    
                def sanitize(obj):
                    if isinstance(obj, bytes):
                        return "<bytes>"
                    if isinstance(obj, dict):
                        return {k: sanitize(v) for k, v in obj.items()}
                    if isinstance(obj, list):
                        return [sanitize(i) for i in obj]
                    return obj
                    
                output_data = sanitize(output_data)
                    
                content_text = ""
                if event.content and event.content.parts:
                    content_text = event.content.parts[0].text
                    
                payload = {
                    "type": "event",
                    "content": content_text,
                    "output": output_data,
                    "route": getattr(event, "route", None),
                    "state": getattr(event, "state", None)
                }
                yield json.dumps(payload) + "\n"
            
        finally:
            if lock_acquired:
                # Forcefully wipe the key from memory immediately after execution
                os.environ.pop("GEMINI_API_KEY", None)
                api_key_lock.release()

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")

from fastapi.staticfiles import StaticFiles
import pathlib
from fastapi.responses import FileResponse, Response

@app.head("/")
async def head_root():
    return Response(status_code=200)

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.get("/")
async def get_root():
    return FileResponse(str(pathlib.Path(__file__).parent.parent / "frontend" / "index.html"))

# Mount remaining static assets (CSS, JS) without intercepting root
app.mount("/", StaticFiles(directory=str(pathlib.Path(__file__).parent.parent / "frontend"), html=False), name="frontend")

if __name__ == "__main__":
    import uvicorn
    # uvicorn app.server:app --reload
    uvicorn.run("app.server:app", host="0.0.0.0", port=8000, reload=True)
