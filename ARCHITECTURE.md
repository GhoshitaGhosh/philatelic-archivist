# Philatelic Archivist Architecture

## 1. System State Schema

The ADK 2.0 graph workflow dynamically tracks the following critical components within the `Event` state or the node inputs:

| State Key / Field | Source | Description |
|-------------------|--------|-------------|
| `heritage_flag` | `input_guardrail_node` | Boolean indicating if the artifact is over 100 years old (Antiquities Act compliance). |
| `ocr_results` | `visual_ocr_node` | Structured JSON containing denomination, postmark dates, locations, and extracted visual tokens. |
| `milestone_results`| `chronological_context_node`| The synthesized historical summary linking the artifact to the deterministic `historical_registry.json`. |
| `philatelic_data` | `archival_synthesis_node`| The final validated struct schema rendered directly into the frontend. |
| `historical_story_map`| `archival_synthesis_node`| The engaging narrative context bridging the extracted traits and the milestone database. |

## 2. Node Execution Lifecycles

Our directed acyclic graph (DAG) leverages four robust nodes:

* **Input Guardrail Node**: An initial Python-based security checkpoint. It extracts text payloads from multimodal inputs and intercepts explicit financial valuation requests (e.g., "worth", "price"). Crucially, it preserves the incoming Base64 image payload as an unmodified `types.Part.from_bytes()` object in the ADK global state so subsequent nodes have full visual access. It routes `flagged` to immediate rejection, and `passed` to the primary graph.
* **Visual / OCR Node**: An `LlmAgent` currently defaulted to `gemini-3.1-flash-lite`. It operates natively on the multimodal image payload to extract faint cachets, watermarks, and postmark dates using zero-shot vision. The output is structured strictly via `OCROutput`.
* **Prepare Context Node**: An intermediate state-bridging node. Because sequential LlmAgents traditionally only pass text schemas, this node fetches the original multimodal image from the ADK state and stitches it together with the OCR extraction text, guaranteeing the next node isn't flying blind.
* **Chronological Context Node**: An `LlmAgent` tasked with deterministic grounding. Equipped with both the OCR text and full multimodal vision of the physical artifact, it automatically calls the `query_historical_database` tool (which uses a zero-blocking in-memory JSON cache) to link the artifact against verified milestones like the 1950 Republic Day or 1953 Everest issues. If critical historical data is missing, the node dynamically falls back to the `search_online_archives` tool to execute a headless, pure-Python DuckDuckGo HTML scrape from the public web. Through strict prompt engineering, this node is explicitly mandated to extract exact dates and precise years, actively preventing vague LLM hallucinations and filling historical gaps efficiently.
* **Archival Synthesis Node**: The terminal node. It consumes a meticulously aggregated prompt containing the `heritage_flag`, the `ocr_results`, and the `milestone_results`. It outputs the `FinalOutput` schema, generating both the structured Philatelic Schema and the narrative Historical Story Map for frontend rendering.

## 3. NDJSON Buffer Strategy
Because analyzing historical artifacts through three sequential LLM agents takes time, the API must stream intermediate progress to the frontend to prevent connection timeouts and UX friction. We implemented an `application/x-ndjson` (Newline Delimited JSON) StreamingResponse in FastAPI. As the ADK `InMemoryRunner` yields graph events (guardrail rejections, node transitions, token usage, tool calls), they are immediately flushed to the frontend. Crucially, the stream loop is wrapped in a resilient error handler that gracefully intercepts API quotas (e.g., `429 RESOURCE_EXHAUSTED`) and SDK crashes, serializing them into safe NDJSON error chunks that the UI renders seamlessly without terminating the HTTP connection abruptly.

1. **Backend Payload Interception**: The FastAPI `/api/archive` endpoint executes the graph using the `InMemoryRunner`. Because the guardrail node echoes the original multimodal payload (which includes raw image bytes), `json.dumps()` would traditionally throw a `TypeError`. We resolve this with a recursive `sanitize()` function that dynamically strips raw `bytes` from the payload before JSON serialization.
2. **Frontend Defragmentation**: Large LLM token responses (specifically the `historical_story_map` string) often fragment across network packets. Our Vanilla JS frontend leverages a global `chunkBuffer` array. When incomplete JSON strings arrive over the `TextDecoder`, they are caught in a `try/catch` block and buffered. The frontend continuously concatenates incoming chunks until the trailing `\n` allows a successful `JSON.parse()`.
3. **Live JSON Harvesting**: Instead of waiting for the full stream to close, the frontend continuously monitors the incoming `data.content` stream for the substring `{"philatelic_data":`. Once identified, the UI dynamically patches the Archival Passport schema in real-time, delivering an unparalleled user experience.

## 4. Bring Your Own Key (BYOK) Security Architecture

To support free public deployments (e.g., Hugging Face Spaces) without exposing the developer's API quota, the system incorporates a secure BYOK layer:

1. **Dynamic Configuration Probing**: The frontend invokes `GET /api/config` on load. If the server lacks a `.env` configuration, the UI dynamically renders a secure password input for the visitor's API key.
2. **Header-Only Transmission**: The frontend never places the API key in the JSON payload body. It is transmitted exclusively via a custom `X-Gemini-Key` HTTP header.
3. **Single-Tenant Memory Isolation**: Inside the FastAPI `/api/archive` endpoint, if a BYOK key is detected, the server acquires a strict `asyncio.Lock()`. This prevents concurrent requests from cross-contaminating keys. The backend temporarily binds the key to `os.environ` specifically for the ADK `InMemoryRunner` execution context.
4. **Guaranteed Volatility**: Wrapped in an ironclad `finally` block, the server guarantees that the `GEMINI_API_KEY` is explicitly popped from the environment the exact microsecond the event stream concludes, ensuring the key is never logged, leaked, or persisted.

## 5. Unified Docker Deployment

To eliminate the need for cross-origin resource sharing (CORS) complexities in production and ensure frictionless hosting, the application uses a unified monolithic architecture:

1. **Native Static File Serving**: The FastAPI application natively mounts the `/frontend` directory via Starlette's `StaticFiles`. Instead of running two independent servers, the backend serves the glassmorphic HTML/CSS/JS payload directly on the root `GET /` endpoint.
2. **Containerized Port Binding**: Designed specifically for **Hugging Face Spaces**, the entire application is containerized using a minimal Dockerfile powered by `uv` for lightning-fast environment syncing. The `uvicorn` ASGI server binds aggressively to `0.0.0.0:7860`, intercepting the reverse-proxy ingress traffic from Hugging Face's load balancers without requiring any specialized WSGI configurations.
