"""
Risk Assessment Test Suite
Run: python3 risk_assessor_test.py
"""

import asyncio
import sys
from pathlib import Path
import os

# Load .env
try:
    from dotenv import load_dotenv

    env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(env_path)
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

from RiskDetector.risk_assessor import RiskAssessor

# Test cases
TEST_CASES = [
    {
        "name": "Example 1: Exhaustion (LOW)",
        "messages": ["I'm exhausted and nothing feels meaningful anymore."],
        "expected": "LOW",
    },
    {
        "name": "Example 2: Passive SI (MODERATE→HIGH)",
        "messages": ["I don't want to wake up tomorrow honestly."],
        "expected": "HIGH",  # Passive SI with temporal specificity warrants HIGH
    },
    {
        "name": "Example 3: Temporal urgency (HIGH)",
        "messages": ["Tonight feels different. I think I'm done."],
        "expected": "HIGH",
    },
    {
        "name": "Example 4: Goodbye behavior (IMMINENT)",
        "messages": ["I already wrote goodbye messages."],
        "expected": "IMMINENT",
    },
    {
        "name": "Multi-turn escalation (MODERATE→HIGH)",
        "messages": [
            "I'm tired of existing honestly.",
            "Nobody would even notice if I disappeared.",
            "Tonight feels different.",
        ],
        "memory_summary": {
            "hopelessness_trend": "increasing",
            "social_isolation": "high",
        },
        "expected": "MODERATE",  # Passive SI across turns, but no active ideation yet
    },
    {
        "name": "Example 5: Normal sadness (LOW)",
        "messages": ["I've been feeling down lately. Work has been stressful."],
        "expected": "LOW",
    },
    {
        "name": "Example 6: Severe hopelessness (MODERATE)",
        "messages": [
            "Nothing ever changes. I've tried everything.",
            "I'm just going through the motions.",
        ],
        "expected": "MODERATE",
    },
]


async def run_tests():
    """Run all test cases"""
    assessor = RiskAssessor()
    passed = 0
    failed = 0

    print("\n" + "=" * 70)
    print("RISK ASSESSMENT MODULE TEST SUITE")
    print("=" * 70 + "\n")

    for i, test in enumerate(TEST_CASES, 1):
        print(f"Test {i}: {test['name']}")
        print("-" * 70)

        try:
            result = await assessor.assess(
                messages=test["messages"],
                memory_summary=test.get("memory_summary"),
            )

            print(f"Input Messages:")
            for msg in test["messages"]:
                print(f"  • {msg}")

            if test.get("memory_summary"):
                print(f"Memory Summary: {test['memory_summary']}")

            print(f"\nResult:")
            print(
                f"  Risk Level: {result['risk_level']} (expected: {test['expected']})"
            )
            print(f"  Confidence: {result['confidence']:.2f}")
            print(
                f"  Signals: {', '.join(result['signals']) if result['signals'] else 'None'}"
            )
            print(f"  Reasoning: {result['reasoning']}")

            # Check if result matches expected
            if result["risk_level"] == test["expected"]:
                print("✓ PASS")
                passed += 1
            else:
                print("✗ FAIL")
                failed += 1

        except Exception as e:
            print(f"✗ ERROR: {e}")
            failed += 1

        print()

    # Summary
    print("=" * 70)
    print(f"SUMMARY: {passed} passed, {failed} failed out of {len(TEST_CASES)} tests")
    print("=" * 70 + "\n")

    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(run_tests())
    sys.exit(0 if success else 1)
