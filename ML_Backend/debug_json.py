#!/usr/bin/env python3
"""Debug script to see exact JSON from model"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from dotenv import load_dotenv
import json

load_dotenv()

test_input = "yeah i just cracked a glass and he called me stupid and worthless and amistake"

system_prompt = """You are a psychological risk assessment expert. Analyze the user's message for suicide/self-harm risk.

Respond ONLY with valid JSON in this exact format:
{
  "risk_level": "NONE|LOW|MODERATE|HIGH|IMMINENT",
  "signals_detected": [list of detected risk signals],
  "confidence": 0-1,
  "reasoning": "brief explanation"
}"""

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
    
    response = llm.invoke(messages)
    
    # Extract text from list
    if isinstance(response.content, list):
        for block in response.content:
            if isinstance(block, dict) and block.get('type') == 'text':
                response_text = block.get('text', '')
                break
    else:
        response_text = response.content.strip()
    
    # Extract JSON
    if "```json" in response_text:
        extracted = response_text.split("```json")[1].split("```")[0].strip()
    elif "```" in response_text:
        first = response_text.find('{')
        last = response_text.rfind('}')
        extracted = response_text[first:last+1] if first != -1 and last != -1 else response_text
    else:
        first = response_text.find('{')
        last = response_text.rfind('}')
        extracted = response_text[first:last+1] if first != -1 and last != -1 else response_text
    
    print("Extracted JSON (raw repr):")
    print(repr(extracted))
    print("\n" + "="*80)
    print("Extracted JSON (formatted):")
    print(extracted)
    print("\n" + "="*80)
    
    # Try to parse with detailed error
    try:
        parsed = json.loads(extracted)
        print("\n✓ Valid JSON, parsed successfully")
        print(json.dumps(parsed, indent=2))
    except json.JSONDecodeError as e:
        print(f"\n✗ JSON Error: {e}")
        print(f"Error location - char {e.pos}: {repr(extracted[max(0, e.pos-20):e.pos+20])}")
        
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
