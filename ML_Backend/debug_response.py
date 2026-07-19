#!/usr/bin/env python3
"""Debug script to print raw response from Gemma 4 31B for problematic input."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from dotenv import load_dotenv
import json

load_dotenv()

# Test input that's causing issues
test_input = (
    "yeah i just cracked a glass and he called me stupid and worthless and amistake"
)

# Risk assessment system prompt (same as in risk_assessor.py)
system_prompt = """You are a psychological risk assessment expert. Analyze the user's message for suicide/self-harm risk.

Respond ONLY with valid JSON in this exact format:
{
  "risk_level": "NONE|LOW|MODERATE|HIGH|IMMINENT",
  "signals_detected": [list of detected risk signals],
  "confidence": 0-1,
  "reasoning": "brief explanation"
}

Risk levels:
- NONE: No risk indicators
- LOW: Minor distress or negative thoughts
- MODERATE: Passive suicidal ideation or self-harm urges
- HIGH: Active suicidal ideation or plan
- IMMINENT: Immediate danger, imminent action

Signals to detect: suicidal_ideation, self_harm_urges, hopelessness, social_isolation, substance_abuse, trauma_mention, active_planning, goodbye_language, temporal_urgency, dependency_on_chatbot, distress_signals, passive_suicidal_ideation"""

try:
    llm = ChatGoogleGenerativeAI(
        model="gemma-4-31b-it",
        temperature=0.3,
        max_output_tokens=512,
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=test_input),
    ]

    print("=" * 80)
    print("Testing input:")
    print(f"  {test_input}")
    print("=" * 80)
    print("\nCalling Gemma 4 31B...")

    response = llm.invoke(messages)

    print("\nRaw response type:", type(response.content))
    print("\nRaw response.content:")
    print(repr(response.content))

    print("\n" + "=" * 80)
    print("Formatted output:")
    print(response.content)
    print("=" * 80)

    # Try to parse it as JSON
    try:
        if isinstance(response.content, list):
            response_text = ""
            for block in response.content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        response_text = block.get("text", "")
                        break
                elif isinstance(block, str):
                    response_text = block
                    break
            if not response_text:
                response_text = "\n".join(str(b) for b in response.content)
        else:
            response_text = response.content.strip()

        print("\nExtracted text:")
        print(repr(response_text))

        parsed = json.loads(response_text)
        print("\nSuccessfully parsed as JSON:")
        print(json.dumps(parsed, indent=2))
    except json.JSONDecodeError as e:
        print(f"\nJSON parsing failed: {e}")
        print(f"Response text: {repr(response_text)}")

except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
    import traceback

    traceback.print_exc()
