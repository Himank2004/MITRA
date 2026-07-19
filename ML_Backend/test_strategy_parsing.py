#!/usr/bin/env python3
"""Test StrategyBot response parsing with detailed debugging"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
import re
import json

load_dotenv()

# Test conversation
test_conversation = """usr: I'm feeling anxious about finding work
sys: So you're anxious about the job search?
usr: Yes, I keep trying but feel like I'm not getting anywhere.
sys: That must be frustrating. Have you thought about what kind of work appeals to you?
usr: I'm not sure. I think I might need to try something new."""

system_prompt = """Your task is to analyze a conversation and predict the therapy strategy to use when responding to the newest user message. Before giving your final answer, explain your reasoning step-by-step, showing how earlier parts of the conversation led to your prediction. Finally, output the final predicted strategies as a comma-separated list.

The possible strategies are:
Stage 1 — Exploration: Question, Restatement or Paraphrasing
Stage 2 — Comforting: Reflection of Feelings, Perspective-taking, Affirmation and Reassurance
Stage 3 — Action: Providing Suggestions, Information, Others

Format your response with:
Reasoning: [explanation]
Final Answer: [strategy1, strategy2, ...]"""

def _parse_strategy_response(text: str):
    """Parse Reasoning / Final Answer block from model output."""
    print(f"\n[DEBUG] Parsing text (length={len(text)})")
    print(f"[DEBUG] Text (first 500 chars):\n{text[:500]}")
    
    pattern = re.compile(
        r"(?s)Reasoning:\s*(?P<reasoning>.*?)\s*Final Answer:\s*(?P<strategy>.+)$"
    )
    match = pattern.search(text)
    reasoning = ""
    strategy_list = []
    if match:
        reasoning = match.group("reasoning").strip()
        strategy_list = [s.strip() for s in match.group("strategy").split(",")]
        print(f"[DEBUG] Match found!")
        print(f"[DEBUG] Reasoning: {reasoning[:100]}...")
        print(f"[DEBUG] Strategy raw: {match.group('strategy')}")
        print(f"[DEBUG] Strategy list: {strategy_list}")
    else:
        print(f"[DEBUG] No regex match found!")
        # Try to find Final Answer manually
        if "Final Answer:" in text:
            parts = text.split("Final Answer:")
            print(f"[DEBUG] Found 'Final Answer:' marker")
            if len(parts) > 1:
                strategy_part = parts[1].strip()
                print(f"[DEBUG] Strategy part: {strategy_part[:200]}")
        
    return reasoning, strategy_list

try:
    # Test with Llama
    print("="*80)
    print("Testing with Llama 3.3 70B...")
    print("="*80)
    
    llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.5)
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", f"Conversation:\n{test_conversation}")
    ])
    
    chain = prompt | llm
    response = chain.invoke({})
    
    print(f"\nResponse type: {type(response)}")
    print(f"Response.content type: {type(response.content)}")
    print(f"\nRaw response.content:\n{response.content}")
    
    print("\n" + "="*80)
    print("Parsing response...")
    print("="*80)
    
    reasoning, strategy_list = _parse_strategy_response(response.content)
    
    print(f"\nFinal result:")
    print(f"  Reasoning: {reasoning[:100]}...")
    print(f"  Strategies: {strategy_list}")
    
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
