# RiskDetector

Psychological risk assessment and dynamic safety policy injection for TherapyBot.

## Quick Integration

```python
from RiskDetector import RiskAssessor, PolicyInjector

# RiskAssessor analyzes conversation for risk
risk = await assessor.assess(messages)
# Returns: {risk_level, confidence, signals, reasoning}

# PolicyInjector maps risk to safety policy
policy = PolicyInjector.get_policy_block(
    PolicyInjector.determine_mode(risk)
)
```

## Risk Levels

- NONE: Normal emotional distress
- LOW: Burnout, mild hopelessness
- MODERATE: Passive SI, numbness
- HIGH: Active SI, escalation
- IMMINENT: Intent, planning, goodbye

## Policy Modes

- NORMAL_SUPPORT: No additional policy
- SUPPORTIVE_MONITORING: Gentle, validating
- GENTLE_ASSESSMENT: Short responses, max 1 question
- CRISIS_ASSESSMENT: Direct safety focus
- EMERGENCY_ESCALATION: Crisis resources included

## Features

✅ Async + sync support  
✅ Groq Llama 3.1 8B LLM  
✅ LLM-based signal extraction  
✅ Deterministic safety overrides  
✅ Query size limiting (4000 chars)  
✅ Crisis resources (Indian hotlines)  
✅ Dependency detection

## Files

- `risk_assessor.py` - Main assessment class
- `policy_injector.py` - Policy system
- `__init__.py` - Exports
- `risk_assessor_test.py` - Tests (7/7 passing)

## Integration Status

✅ **INTEGRATED INTO THERAPYBOT** (`agent_stream.py`)

Risk assessment runs in parallel with emotion/strategy detection and is injected into the message context for dynamic safety policy application.
