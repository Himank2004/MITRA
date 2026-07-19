#!/usr/bin/env python3
"""Test the JSON extraction logic"""

import json

response_text = '''```json
{
  "risk_level": "LOW",
  "signals_detected": [
    "distress_signals",
    "trauma_mention"
  ],
  "confidence": 0.9,
  "reasoning": "The user is reporting emotional abuse and verbal insults from another person, which indicates psychological distress, but there are no expressions of self-harm or suicidal ideation."
}
```'''

print("Original response_text:")
print(repr(response_text))
print("\n" + "="*80)

# Extract JSON from markdown if present
if "```json" in response_text:
    print("Found ```json marker")
    response_text = response_text.split("```json")[1]
    print("After split on ```json:")
    print(repr(response_text))
    
    response_text = response_text.split("```")[0].strip()
    print("After split on ``` and strip:")
    print(repr(response_text))

print("\n" + "="*80)
print("Trying to parse as JSON:")
try:
    result = json.loads(response_text)
    print("Success!")
    print(json.dumps(result, indent=2))
except json.JSONDecodeError as e:
    print(f"Failed: {e}")
    print(f"Response text to parse: {repr(response_text)}")
