#!/usr/bin/env python3
"""Test with detailed tracing through the actual risk_assessor code"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
import json
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from dotenv import load_dotenv

load_dotenv()

test_input = "yeah i just cracked a glass and he called me stupid and worthless and amistake"

# System prompt from risk_assessor
system_prompt = """You are a psychological risk assessment expert. Analyze the message for psychological risk signals.

Respond ONLY with valid JSON:
{
  "risk_level": "NONE|LOW|MODERATE|HIGH|IMMINENT",
  "signals_detected": [list of signals],
  "confidence": 0-1,
  "reasoning": "explanation"
}

Risk levels:
- NONE: No risk indicators
- LOW: Minor distress or negative thoughts
- MODERATE: Passive suicidal ideation or self-harm urges
- HIGH: Active suicidal ideation or plan
- IMMINENT: Immediate danger, imminent action
"""

def _extract_json_from_response(response_text: str) -> str:
    """Extract JSON from response, handling markdown code fences."""
    # Try to extract from markdown code fence (```json ... ```)
    if "```json" in response_text:
        try:
            json_part = response_text.split("```json")[1]
            json_part = json_part.split("```")[0].strip()
            if json_part:
                return json_part
        except (IndexError, ValueError):
            pass
    
    # Try to extract from generic code fence (``` ... ```)
    if "```" in response_text:
        try:
            parts = response_text.split("```")
            # Look for a part that starts with { (likely JSON)
            for part in parts:
                stripped = part.strip()
                if stripped.startswith("{"):
                    return stripped
            # If no { found, try the middle part (between first ``` markers)
            if len(parts) >= 3:
                middle = parts[1].strip()
                if middle:
                    return middle
        except (IndexError, ValueError):
            pass
    
    # Try to extract JSON object directly from the text
    # Find first { and last } 
    first_brace = response_text.find('{')
    last_brace = response_text.rfind('}')
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        json_part = response_text[first_brace:last_brace+1]
        if json_part.strip():
            return json_part
    
    # Return original if no extraction worked
    return response_text.strip()

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
    
    print("Response type:", type(response.content))
    print("\nResponse content structure:")
    if isinstance(response.content, list):
        for i, block in enumerate(response.content):
            print(f"  Block {i}: {type(block)} - ", end="")
            if isinstance(block, dict):
                print(f"keys={list(block.keys())}")
                if 'type' in block:
                    print(f"    type={block['type']}")
            else:
                print(f"length={len(block)}")
    
    print("\n" + "="*80)
    
    # Extract response_text (simulating _call_llm_sync logic)
    response_text = ""
    if isinstance(response.content, list):
        for block in response.content:
            if isinstance(block, dict):
                if block.get('type') == 'text':
                    response_text = block.get('text', '')
                    print(f"Extracted from text block: {len(response_text)} chars")
                    break
            elif isinstance(block, str):
                response_text = block
                print(f"Extracted from string block: {len(response_text)} chars")
                break
        
        if not response_text:
            print("No direct block extraction, concatenating all blocks...")
            text_blocks = []
            for block in response.content:
                if isinstance(block, dict):
                    text_value = block.get('text', '')
                    if not text_value:
                        text_value = block.get('thinking', '')
                    if text_value:
                        text_blocks.append(text_value)
                elif isinstance(block, str):
                    text_blocks.append(block)
            
            if text_blocks:
                response_text = '\n'.join(text_blocks)
                print(f"Concatenated {len(text_blocks)} text blocks: {len(response_text)} chars")
    else:
        response_text = response.content.strip()
    
    print(f"\nResponse text (first 200 chars):\n{response_text[:200]}")
    
    print("\n" + "="*80)
    print("Extracting JSON...")
    extracted_json = _extract_json_from_response(response_text)
    print(f"Extracted JSON ({len(extracted_json)} chars):")
    print(repr(extracted_json[:200]))
    
    print("\n" + "="*80)
    print("Parsing JSON...")
    try:
        result = json.loads(extracted_json)
        print("✓ Success!")
        print(json.dumps(result, indent=2))
    except json.JSONDecodeError as e:
        print(f"✗ JSON Error: {e}")
        print(f"Error at char {e.pos}: {repr(extracted_json[max(0, e.pos-30):e.pos+30])}")
        
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
