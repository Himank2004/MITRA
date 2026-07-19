#!/usr/bin/env python3
"""Debug script to see full response and JSON extraction"""

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
    
    print("Full response text:")
    print("=" * 80)
    print(response_text)
    print("=" * 80)
    
    # Try different extraction methods
    print("\nMethod 1: Extract from ```json ... ```")
    if "```json" in response_text:
        extracted = response_text.split("```json")[1].split("```")[0].strip()
        print("Extracted:")
        print(extracted)
        try:
            parsed = json.loads(extracted)
            print("✓ Valid JSON")
        except json.JSONDecodeError as e:
            print(f"✗ Invalid JSON: {e}")
    
    print("\n" + "=" * 80)
    print("\nMethod 2: Extract from ``` ... ```")
    if "```" in response_text and "```json" not in response_text:
        extracted = response_text.split("```")[1].strip()
        print("Extracted:")
        print(extracted)
        try:
            parsed = json.loads(extracted)
            print("✓ Valid JSON")
        except json.JSONDecodeError as e:
            print(f"✗ Invalid JSON: {e}")
    
    print("\n" + "=" * 80)
    print("\nMethod 3: Extract { to }")
    first = response_text.find('{')
    last = response_text.rfind('}')
    if first != -1 and last != -1:
        extracted = response_text[first:last+1]
        print("Extracted:")
        print(extracted)
        try:
            parsed = json.loads(extracted)
            print("✓ Valid JSON")
        except json.JSONDecodeError as e:
            print(f"✗ Invalid JSON: {e}")
            
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
