import os
from pydantic import BaseModel, Field
from typing import Optional

from google.adk.workflow import Workflow, START, node
from google.adk.apps import App
from google.adk.agents import LlmAgent
from google.adk.agents.context import Context

from .tools import query_historical_database
from .guardrails import input_guardrail_node, secure_rejection_output

class PhilatelicSchema(BaseModel):
    denomination: Optional[str] = Field(None, description="Stamp denomination")
    postmark_date: Optional[str] = Field(None, description="Postmark or cancellation date")
    issue_location: Optional[str] = Field(None, description="Location of cancellation or issue")
    cancellation_type: Optional[str] = Field(None, description="Type of cancellation")
    perforation_watermark: Optional[str] = Field(None, description="Perforation or watermark details")

class FinalOutput(BaseModel):
    philatelic_data: PhilatelicSchema
    historical_story_map: str = Field(description="An engaging narrative Historical Story Map")

class OCROutput(BaseModel):
    extracted_tokens: str = Field(description="Summary of extracted philatelic visual tokens")

class ContextOutput(BaseModel):
    milestone_summary: str = Field(description="Summary of historical milestone alignments")

visual_ocr_node = LlmAgent(
    name="visual_ocr_node",
    model="gemini-3.1-flash-lite",
    instruction="""Extract philatelic-specific visual tokens from the input, including stamp denomination, 
    postmark dates, cancellation post office locations, and First Day Cover cachet/artwork features.""",
    output_schema=OCROutput,
    output_key="ocr_results"
)

chronological_context_node = LlmAgent(
    name="chronological_context_node",
    model="gemini-3.1-flash-lite",
    instruction="""You are the Chronological Context Node. You will receive OCR extracted tokens.
    Use the query_historical_database tool to link the extracted dates/locations to historical milestones. 
    Summarize the milestone context and historical significance.""",
    tools=[query_historical_database],
    output_schema=ContextOutput,
    output_key="milestone_results"
)

@node
def prepare_synthesis(ctx: Context, node_input: dict) -> str:
    """Gather all state data and prepare the prompt for the synthesis node."""
    ocr = ctx.state.get("ocr_results", {})
    heritage = ctx.state.get("heritage_flag", False)
    milestone = node_input
    
    prompt = f"""
    Heritage Flag (>100 years old): {heritage}
    OCR Extraction: {ocr}
    Chronological Context: {milestone}
    
    Please synthesize this into the final catalog.
    """
    return prompt

archival_synthesis_node = LlmAgent(
    name="archival_synthesis_node",
    model="gemini-3.1-flash-lite",
    instruction="""You are the Archival Synthesis Node. Combine the visual/OCR extraction data, the chronological context, 
    and any heritage flags to produce a comprehensive final catalog. 
    You must output a structured Philatelic Schema AND an engaging narrative 'Historical Story Map'.""",
    output_schema=FinalOutput
)

root_agent = Workflow(
    name="philatelic_workflow",
    edges=[
        (START, input_guardrail_node),
        (input_guardrail_node, {
            "flagged": secure_rejection_output,
            "passed": visual_ocr_node
        }),
        (visual_ocr_node, chronological_context_node),
        (chronological_context_node, prepare_synthesis),
        (prepare_synthesis, archival_synthesis_node),
    ]
)

app = App(
    root_agent=root_agent,
    name="app",
)
