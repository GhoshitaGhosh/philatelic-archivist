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

* **Input Guardrail Node**: An initial Python-based security checkpoint. It extracts text payloads from multimodal inputs and intercepts explicit financial valuation requests (e.g., "worth", "price"). Crucially, it preserves the incoming Base64 image payload as an unmodified `types.Part.from_bytes()` object so the subsequent OCR node has full visual access. It routes `flagged` to immediate rejection, and `passed` to the primary graph.
* **Visual / OCR Node**: An `LlmAgent` currently defaulted to `gemini-3.1-flash-lite`. It operates natively on the multimodal image payload to extract faint cachets, watermarks, and postmark dates using zero-shot vision. The output is structured strictly via `OCROutput`.
* **Chronological Context Node**: An `LlmAgent` tasked with deterministic grounding. It ingests the OCR results and automatically calls the `query_historical_database` tool, scanning `data/historical_registry.json` to link the artifact against verified milestones like the 1950 Republic Day or 1953 Everest issues.
* **Archival Synthesis Node**: The terminal node. It consumes a meticulously aggregated prompt containing the `heritage_flag`, the `ocr_results`, and the `milestone_results`. It outputs the `FinalOutput` schema, generating both the structured Philatelic Schema and the narrative Historical Story Map for frontend rendering.

## 3. NDJSON Buffer Strategy

To bridge the ADK backend with the modern glassmorphic frontend, the project uses a highly resilient NDJSON streaming architecture:

1. **Backend Payload Interception**: The FastAPI `/api/archive` endpoint executes the graph using the `InMemoryRunner`. Because the guardrail node echoes the original multimodal payload (which includes raw image bytes), `json.dumps()` would traditionally throw a `TypeError`. We resolve this with a recursive `sanitize()` function that dynamically strips raw `bytes` from the payload before JSON serialization.
2. **Frontend Defragmentation**: Large LLM token responses (specifically the `historical_story_map` string) often fragment across network packets. Our Vanilla JS frontend leverages a global `chunkBuffer` array. When incomplete JSON strings arrive over the `TextDecoder`, they are caught in a `try/catch` block and buffered. The frontend continuously concatenates incoming chunks until the trailing `\n` allows a successful `JSON.parse()`.
3. **Live JSON Harvesting**: Instead of waiting for the full stream to close, the frontend continuously monitors the incoming `data.content` stream for the substring `{"philatelic_data":`. Once identified, the UI dynamically patches the Archival Passport schema in real-time, delivering an unparalleled user experience.
