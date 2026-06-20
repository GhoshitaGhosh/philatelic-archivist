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

@app.post("/api/archive")
async def archive_endpoint(request: Request):
    """Endpoint that accepts a philatelic description and streams ADK node events back."""
    data = await request.json()
    user_input = data.get("input", "")
    
    async def event_stream():
        # Create a session for the local dev execution
        session = await runner.session_service.create_session(
            app_name="app", user_id="local_ui"
        )
        msg = types.Content(role="user", parts=[types.Part.from_text(text=user_input)])
        
        # Iterate over the graph workflow event stream
        async for event in runner.run_async(
            user_id="local_ui",
            session_id=session.id,
            new_message=msg,
        ):
            output_data = event.output
            if hasattr(output_data, "model_dump"):
                output_data = output_data.model_dump()
                
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

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")

if __name__ == "__main__":
    import uvicorn
    # uvicorn app.server:app --reload
    uvicorn.run("app.server:app", host="0.0.0.0", port=8000, reload=True)
