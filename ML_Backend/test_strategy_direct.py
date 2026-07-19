#!/usr/bin/env python3
"""Test StrategyBot directly to see what's happening"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Enable debug flags before importing
from constants import DEBUG_FLAGS
DEBUG_FLAGS["strategy"] = True

import asyncio
from StrategyBot.bot import predict_therapy_strategy

async def test_strategy_prediction():
    # Test with a realistic conversation (use 'usr' and 'sys' roles)
    history = [
        {"role": "usr", "content": "I'm feeling anxious about finding work"},
        {"role": "sys", "content": "So you're anxious about the job search?"},
        {"role": "usr", "content": "Yes, I keep trying but feel like I'm not getting anywhere."},
        {"role": "sys", "content": "That must be frustrating. Have you thought about what kind of work appeals to you?"},
        {"role": "usr", "content": "I'm not sure. I think I might need to try something new."},
    ]
    
    print("Testing StrategyBot with conversation:")
    for msg in history:
        print(f"  {msg['role']}: {msg['content'][:50]}...")
    
    print("\n" + "="*80)
    print("Calling predict_therapy_strategy...")
    print("="*80 + "\n")
    
    try:
        result = await predict_therapy_strategy(history)
        print(f"\nResult: {result}")
        reasoning, strategies = result
        print(f"\nReasoning (first 100 chars): {reasoning[:100]}")
        print(f"Strategies: {strategies}")
        print(f"Strategies type: {type(strategies)}")
        print(f"Strategies length: {len(strategies)}")
        
        if not strategies:
            print("\n⚠️ WARNING: Empty strategies list!")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_strategy_prediction())
