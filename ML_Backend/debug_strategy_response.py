#!/usr/bin/env python3
"""Debug StrategyBot response extraction"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from StrategyBot.utils import format_conversation, format_messages
import re

# Test conversation
history = [
    {"role": "usr", "content": "I'm feeling anxious about finding work"},
    {"role": "sys", "content": "So you're anxious about the job search?"},
    {"role": "usr", "content": "Yes, I keep trying but feel like I'm not getting anywhere."},
    {"role": "sys", "content": "That must be frustrating. Have you thought about what kind of work appeals to you?"},
    {"role": "usr", "content": "I'm not sure. I think I might need to try something new."},
]

# System prompt from StrategyBot
system_prompt = """Your task is to analyze a conversation and predict the therapy strategy to use when responding to the newest user message. Before giving your final answer, explain your reasoning step-by-step, showing how earlier parts of the conversation led to your prediction. Finally, output the final predicted strategies as a comma-separated list. Try not to use too many strategies at once.

The possible strategies are organised into three stages:

Stage 1 — Exploration (use early in a conversation or when more context is needed):
  Question: Ask for information related to the problem to help the user articulate their situation.
  Restatement or Paraphrasing: Rephrase the user's statements to make their situation clear and show you understand.

Stage 2 — Comforting (use when the user needs emotional support or validation):
  Reflection of Feelings: Articulate and describe the help-seeker's feelings to show empathy and understanding.
  Perspective-taking: Offer grounded perspective and emotional insight when beneficial.
  Affirmation and Reassurance: Affirm the user's strengths and provide reassurance and encouragement.

Stage 3 — Action (use when the user is ready to move forward or needs practical help):
  Providing Suggestions: Offer concrete suggestions about how the user can change or address their situation.
  Information: Provide useful factual information about the user's situation.
  Others: Any response that does not fit the above categories, or a combination too nuanced to label.

Examples:
[truncated for brevity]

Respond in this format:
Reasoning: [step-by-step explanation]
Final Answer: [comma-separated list of strategies]"""

def _extract_response_text(content):
    """Extract text from response.content, handling multiple formats."""
    print(f"[DEBUG] _extract_response_text called")
    print(f"[DEBUG] content type: {type(content)}")
    if isinstance(content, list):
        print(f"[DEBUG] Content is list with {len(content)} items")
        response_text = ""
        for i, block in enumerate(content):
            print(f"[DEBUG] Block {i}: type={type(block)}")
            if isinstance(block, dict):
                if block.get("type") == "text":
                    response_text = block.get("text", "")
                    print(f"[DEBUG] Found text block with {len(response_text)} chars")
                    break
            elif isinstance(block, str):
                response_text = block
                print(f"[DEBUG] Found string block with {len(response_text)} chars")
                break
        if not response_text:
            response_text = "\n".join(str(b) for b in content)
            print(f"[DEBUG] Concatenated all blocks, got {len(response_text)} chars")
    else:
        response_text = str(content).strip()
        print(f"[DEBUG] Direct string, got {len(response_text)} chars")
    
    print(f"[DEBUG] Returning response_text (first 200 chars):\n{response_text[:200]}")
    return response_text

def _parse_strategy_response(text: str):
    """Parse Reasoning / Final Answer block from model output."""
    print(f"\n[DEBUG] _parse_strategy_response called")
    print(f"[DEBUG] text length: {len(text)}")
    print(f"[DEBUG] text (first 300 chars):\n{text[:300]}")
    
    pattern = re.compile(
        r"(?s)Reasoning:\s*(?P<reasoning>.*?)\s*Final Answer:\s*(?P<strategy>.+)$"
    )
    match = pattern.search(text)
    reasoning = ""
    strategy_list = []
    if match:
        reasoning = match.group("reasoning").strip()
        strategy_raw = match.group("strategy").strip()
        print(f"[DEBUG] Match found!")
        print(f"[DEBUG] Strategy raw (first 200 chars): {strategy_raw[:200]}")
        strategy_list = [s.strip() for s in strategy_raw.split(",")]
        print(f"[DEBUG] Strategy list: {strategy_list}")
    else:
        print(f"[DEBUG] NO REGEX MATCH!")
        # Debug - show what markers are present
        if "Reasoning:" in text:
            print(f"[DEBUG] 'Reasoning:' found at position {text.find('Reasoning:')}")
        if "Final Answer:" in text:
            print(f"[DEBUG] 'Final Answer:' found at position {text.find('Final Answer:')}")
    
    return reasoning, strategy_list

# Format conversation
try:
    conversation = format_conversation(history)
    print("Formatted conversation:")
    print(conversation)
    print("\n" + "="*80 + "\n")
    
    # Build and invoke chain
    llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.5)
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", f"Conversation:\n{conversation}")
    ])
    
    chain = prompt | llm
    response = chain.invoke({})
    
    print(f"Raw response type: {type(response)}")
    print(f"Raw response.content type: {type(response.content)}")
    
    # Extract
    response_text = _extract_response_text(response.content)
    
    # Parse
    reasoning, strategies = _parse_strategy_response(response_text)
    
    print(f"\n\nFinal result:")
    print(f"  Reasoning: {reasoning[:100]}")
    print(f"  Strategies: {strategies}")
    
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
