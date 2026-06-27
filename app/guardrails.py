import re
from google.adk.events.event import Event
from google.genai import types

def input_guardrail_node(node_input) -> Event:
    """
    Input Guardrail Node: Validates input to ensure safety and compliance.
    """
    # node_input from START could be types.Content if no schema is specified.
    text_input = ""
    if isinstance(node_input, types.Content):
        for part in node_input.parts:
            if getattr(part, "text", None):
                text_input += part.text + " "
    else:
        text_input = str(node_input)
        
    input_lower = text_input.lower()
    
    # Financial Guardrail: Reject monetary valuations
    forbidden_words = ["worth", "value", "appraisal", "price", "how much"]
    if any(word in input_lower for word in forbidden_words):
        return Event(
            content=types.Content(role="model", parts=[types.Part.from_text(text="[GUARDRAIL REJECTION] Financial appraisals and monetary valuations are not permitted.")]),
            route="flagged",
            output="Rejected: Valuation Request"
        )
        
    # Antiquities and Art Treasures Act, 1972 age check
    # Check if item is > 100 years old (i.e. < 1926)
    heritage_flag = False
    years = re.findall(r'\b(1[0-8]\d{2}|19[0-1]\d|192[0-6])\b', input_lower)
    if years:
        heritage_flag = True
        
    # Pass along the ORIGINAL input (preserving the image!) and the heritage flag in the state
    return Event(
        output=node_input,
        route="passed",
        state={
            "heritage_flag": heritage_flag,
            "original_payload": node_input
        }
    )

def secure_rejection_output(node_input: str) -> Event:
    return Event(
        output=node_input,
        content=types.Content(role="model", parts=[types.Part.from_text(text=node_input)])
    )
