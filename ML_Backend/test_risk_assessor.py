#!/usr/bin/env python3
"""Test the risk assessor with the problematic input"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
from RiskDetector.risk_assessor import RiskAssessor

async def main():
    test_input = "yeah i just cracked a glass and he called me stupid and worthless and amistake"
    
    assessor = RiskAssessor()
    
    print("Testing with input:")
    print(f"  {test_input}")
    print("\n" + "="*80)
    
    try:
        result = await assessor.assess([test_input])
        print("\nSuccess! Risk assessment result:")
        import json
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"\nError: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
