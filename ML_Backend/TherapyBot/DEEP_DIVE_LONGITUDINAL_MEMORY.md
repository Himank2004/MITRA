# Longitudinal Memory System - Deep Dive

## System Overview Diagram

```
CONVERSATION FLOW
│
├─ Message 1: User shares anxiety about work
├─ Message 2: Agent responds
├─ Message 3: User talks more
├─ Message 4: Agent suggests grounding
├─ Message 5: User says "that helped"
│
└─ [MESSAGE COUNT = 5] ──► TRIGGER SESSION STATE UPDATE
                               │
                               ├─ SessionStateManager.extract_session_state()
                               │  (Uses small LLM to analyze messages)
                               │
                               ├─ Returns:
                               │  {
                               │    "riskTrend": "improving",
                               │    "activeThemes": ["work_anxiety"],
                               │    "activeWarningSignals": [],
                               │    "whatHelpedThisSession": ["grounding"]
                               │  }
                               │
                               └─ Save to SessionState collection
                                   │
                                   └─ Increment profile_update_counter
                                      │
                                      If counter >= 10:
                                      └─ UserProfileManager.aggregate_sessions_into_profile()
                                         (NO LLM - statistical only)
                                         │
                                         └─ Save to UserProfile collection
```

---

## 1. THEME DEDUPLICATOR - Semantic Clustering

### What It Does

Groups similar psychological concepts into one "theme" to avoid redundancy in the user profile.

**Problem it solves:**

```
Without deduplication:
recurringThemes = ["perfectionism", "fear of failure", "need to be perfect"]
                   ↑ These 3 are basically the same thing!

With deduplication:
recurringThemes = ["perfectionism"] (frequency: 3)
                   ↑ Cleaner, more actionable
```

### How It Works: Cosine Similarity

```
Step 1: Convert text to embeddings (all-mpnet-base-v2)
────────────────────────────────────────────────────

"perfectionism"          →  [0.12, -0.45, 0.89, ..., 0.33]  (768 dimensions)
"need to be perfect"     →  [0.11, -0.44, 0.87, ..., 0.34]
"fear of failure"        →  [0.21, -0.33, 0.78, ..., 0.42]

Step 2: Calculate cosine similarity between each pair
────────────────────────────────────────────────────

Cosine Similarity = (A · B) / (||A|| * ||B||)

Where:
  · = dot product (multiply corresponding dimensions, sum them)
  ||A|| = magnitude (length) of vector A
  ||B|| = magnitude (length) of vector B

Example:
perfectionism vs need_to_be_perfect:
  Cosine Similarity = 0.98  (very similar!)

perfectionism vs fear_of_failure:
  Cosine Similarity = 0.82  (reasonably similar)

perfectionism vs "social anxiety":
  Cosine Similarity = 0.34  (not similar)

Step 3: Apply threshold (0.75)
───────────────────────────────

if similarity >= 0.75:
  MERGE these themes
else:
  KEEP as separate theme
```

### Concrete Example

```python
# Initial themes extracted across 3 sessions:
session_1: ["perfectionism", "work stress"]
session_2: ["perfectionism", "fear of failing"]
session_3: ["need to be perfect", "burnout"]

# Pass to deduplicator:
deduplicator = ThemeDeduplicator(similarity_threshold=0.75)

# Collected all themes:
all_themes = ["perfectionism", "work stress", "perfectionism", "fear of failing",
              "need to be perfect", "burnout"]

# Count frequency:
counter = {
  "perfectionism": 2,
  "work stress": 1,
  "fear of failing": 1,
  "need to be perfect": 1,
  "burnout": 1
}

# Embed each unique theme:
embeddings = {
  "perfectionism": [0.12, -0.45, ..., 0.33],
  "work stress": [-0.02, 0.33, ..., -0.11],
  "fear of failing": [0.14, -0.41, ..., 0.35],
  "need to be perfect": [0.11, -0.44, ..., 0.34],
  "burnout": [-0.15, 0.22, ..., 0.18]
}

# Deduplication algorithm:
for each existing theme:
  find most similar existing theme

perfectionism vs need_to_be_perfect: sim=0.98 (>0.75) → MERGE!
  best_match = perfectionism
  perfectionism.frequency += 1  # Now: 3

perfectionism vs fear_of_failing: sim=0.82 (>0.75) → MERGE!
  best_match = perfectionism
  perfectionism.frequency += 1  # Now: 4

work_stress vs burnout: sim=0.71 (<0.75) → NO MERGE
  Keep both as separate

work_stress vs fear_of_failing: sim=0.45 (<0.75) → NO MERGE

# Final result:
userProfile.recurringThemes = [
  {
    "theme": "perfectionism",
    "frequency": 4,
    "embedding": [0.12, -0.45, ..., 0.33],
    "trend": "stable"
  },
  {
    "theme": "work stress",
    "frequency": 1,
    "embedding": [-0.02, 0.33, ..., -0.11],
    "trend": null
  },
  {
    "theme": "burnout",
    "frequency": 1,
    "embedding": [-0.15, 0.22, ..., 0.18],
    "trend": null
  }
]
```

### Why This Matters

**Without deduplication:**

- User profile becomes cluttered with near-duplicates
- Frontend has to pick which to display
- Same concept appears under different names
- Loses "true frequency" of the underlying pattern

**With deduplication:**

- Clean, unified themes
- "Perfectionism" now shows it appeared 4 times (stronger signal)
- Frontend can show trending themes confidently
- Analytics can correlate with effectiveness

### Threshold Tuning

```
threshold = 0.65   → Too permissive (merges "anxiety" and "anger")
threshold = 0.75   → Balanced (recommended)
threshold = 0.85   → Too strict (keeps "perfectionism" and "need to be perfect" separate)
threshold = 0.95   → Very strict (almost exact matches only)
```

---

## 2. SESSION STATE MANAGER - Real-Time Extraction

### What It Does

Analyzes last ~15 messages and extracts what's happening _right now_ in the conversation.

Called every ~5 messages or when risk spikes.

### Flow: Message → LLM → Extraction

```
INPUT: Last 15 messages
────────────────────────

User: "I've been feeling so burned out at work lately"
Agent: "That sounds really difficult. Burnout can affect so many areas of life."
User: "Yeah, I can't focus, I'm exhausted all the time"
Agent: "Have you tried taking short breaks during the day?"
User: "I tried that yesterday actually - it helped a little bit!"

         ↓

FORMAT FOR LLM
──────────────

Messages get formatted as:
User: I've been feeling so burned out at work lately
Agent: That sounds really difficult. Burnout can affect...
User: Yeah, I can't focus, I'm exhausted all the time
Agent: Have you tried taking short breaks during the day?
User: I tried that yesterday actually - it helped a little bit!

         ↓

SEND TO LLM
───────────

Prompt: "Analyze this conversation snippet and extract:
1. risk_trend: (stable|worsening|improving|volatile)
2. active_themes: [list of 2-4 themes]
3. active_warning_signals: [list if present]
4. what_helped_this_session: [techniques that worked]"

Temperature: 0.3 (low = consistent, not creative)

         ↓

LLM RESPONSE
────────────

{
  "risk_trend": "improving",
  "active_themes": ["burnout", "work_stress", "fatigue"],
  "active_warning_signals": [],
  "what_helped_this_session": ["breaks", "taking_short_breaks"]
}

         ↓

PARSE & CLEAN
──────────────

Extract JSON from markdown backticks if needed
Validate JSON structure
Return parsed dict

         ↓

STORED IN DATABASE
───────────────────

SessionState collection:
{
  userId: "507f...",
  conversationId: "conv_123",
  riskTrend: "improving",
  activeThemes: ["burnout", "work_stress", "fatigue"],
  activeWarningSignals: [],
  whatHelpedThisSession: ["breaks"],
  messageCount: 15,
  lastDetectedEmotions: ["exhaustion", "relief"],
  lastRiskLevel: 4.2,
  lastRiskConfidence: 0.85,
  updatedAt: "2026-05-22T10:30:00Z"
}
```

### Why Use LLM for This? (Not Statistical)

You could theoretically extract this from detected emotions and risk assessments alone, but LLM is better because:

```
Statistical approach (emotion + risk):
  Input: emotions=["sadness", "anxiety"], risk_level=6
  Output: activeThemes = ["sadness", "anxiety"]
  Problem: Generic, doesn't capture CONTEXT

LLM approach:
  Input: Full conversation + emotions + risk
  Output: activeThemes = ["burnout", "work_stress", "fatigue"]
  Better: Specific, contextual, captures the STORY
```

### Fallback Mechanism

If LLM call fails, fallback to previous state with staleness tracking:

```python
if LLM_extraction_failed:
    previous_state = get_session_state(user_id, conversation_id)
    if previous_state:
        # Reuse previous state but mark as stale
        extracted = {
            "risk_trend": previous_state["riskTrend"],
            "active_themes": previous_state["activeThemes"],
            ...
        }
        staleness = previous_state["staleness"] + 1
    else:
        # No previous state, use neutral defaults
        extracted = {...default values...}
        staleness = 0
else:
    # Fresh extraction succeeded
    extracted = {...}
    staleness = 0
```

**Staleness Field Usage:**

```
staleness = 0
  → Fresh extraction (LLM just ran)
  → Agent can fully trust this state

staleness = 1
  → One update old (fallback from previous state, LLM failed once)
  → Agent should use with slight caution

staleness = 2+
  → Very stale (LLM failed multiple times)
  → Agent should note reduced confidence
  → May want to request explicit user feedback

Agent can check staleness in prompt:
"Current session state (freshness: {staleness})"
or
"Warning: Session state is 2 updates old, trust level: reduced"
```

No error propagation = conversation continues smoothly.

---

## 3. USER PROFILE MANAGER - Statistical Aggregation

### What It Does

Builds a slow-changing user profile by aggregating session states into patterns.

**NO LLM** - purely statistical/deterministic.

### Important Cardinality Notes

```
SessionState Cardinality: ONE per Conversation
───────────────────────────────────────────────

userId + conversationId = unique identifier (not multiple)

Example:
  Conversation 1 (conv_123):
    SessionState(userId="user1", convId="conv_123")  ← ONE document
    Updated every 5 messages: msg 5, 10, 15, 20, ...
    NOT created anew each update, just UPDATED

  Conversation 2 (conv_456):
    SessionState(userId="user1", convId="conv_456")  ← SEPARATE document

  One user can have MULTIPLE SessionStates (one per conversation)
  But each conversation has EXACTLY ONE SessionState

Efficiency: O(n) Not O(n²)
──────────────────────────

Naive approach (❌ BAD):
  When aggregating into profile:
    for each new theme:
      for each existing theme:
        check similarity
  Cost: n² comparisons (explodes with many sessions!)

Smart approach (✓ GOOD):
  Store aggregated counts in UserProfile:
  {
    "theme": "perfectionism",
    "frequency": 12,      ← Stored count
    "embedding": [...],
    "lastSeen": date
  }

  When new SessionState arrives:
    for each new theme from this session:
      check against UserProfile themes (typically 5-10 fixed items)
      update frequency
  Cost: O(n) where n = number of new themes (usually 2-4)

The UserProfile is the aggregation hub.
No O(n²) SessionState-to-SessionState comparisons needed.
```

### The Aggregation Process

```
COLLECT RECENT SESSION STATES
──────────────────────────────

Fetch last 20 SessionState docs for user:

Session 1:
  riskTrend: "stable"
  activeThemes: ["perfectionism", "work_stress"]
  whatHelpedThisSession: ["grounding", "validation"]

Session 2:
  riskTrend: "stable"
  activeThemes: ["perfectionism", "social_anxiety"]
  whatHelpedThisSession: ["grounding"]

Session 3:
  riskTrend: "worsening"
  activeThemes: ["loneliness", "burnout"]
  activeWarningSignals: ["isolation_increasing"]
  whatHelpedThisSession: ["humor"]

... (17 more sessions)

           ↓

STEP 1: AGGREGATE THEMES
────────────────────────

Extract all activeThemes from all 20 sessions:
[
  "perfectionism", "work_stress",
  "perfectionism", "social_anxiety",
  "loneliness", "burnout",
  ...
]

Count frequencies:
{
  "perfectionism": 12,
  "work_stress": 8,
  "social_anxiety": 7,
  "loneliness": 6,
  "burnout": 5,
  ...
}

Sort by frequency (descending):
[
  ("perfectionism", 12),
  ("work_stress", 8),
  ("social_anxiety", 7),
  ("loneliness", 6),
  ("burnout", 5),
]

Deduplicate using ThemeDeduplicator:
  - "perfectionism" vs "need to be perfect": sim=0.98 → MERGE
  - "social_anxiety" vs "fear of socializing": sim=0.81 → MERGE

Final: Top 5 themes (deduped):
[
  {
    "theme": "perfectionism",
    "frequency": 12,
    "embedding": [...],
    "lastSeen": "2026-05-22T10:30:00Z",
    "trend": "stable"  # inferred from sessions
  },
  {
    "theme": "work_stress",
    "frequency": 8,
    "embedding": [...],
    "lastSeen": "2026-05-21T15:00:00Z",
    "trend": "worsening"
  },
  ...
]

           ↓

STEP 2: AGGREGATE TRIGGERS/WARNING SIGNALS
───────────────────────────────────────────

Extract all activeWarningSignals:
[
  "isolation_increasing",
  "hopelessness",
  "isolation_increasing",
  "sleep_disruption",
  ...
]

Count and deduplicate:
{
  "isolation_increasing": 3,
  "hopelessness": 2,
  "sleep_disruption": 2,
}

Rank by frequency → commonTriggers list

           ↓

STEP 3: AGGREGATE HELPFUL APPROACHES
─────────────────────────────────────

Extract all whatHelpedThisSession:
[
  "grounding", "validation",
  "grounding",
  "humor",
  "grounding", "validation",
  ...
]

Count:
{
  "grounding": 14,
  "validation": 9,
  "humor": 5,
  ...
}

Calculate effectiveness:
  effectiveness = 3 + frequency (capped at 10)

  grounding: frequency=14 → effectiveness=min(10, 3+14)=10
  validation: frequency=9 → effectiveness=min(10, 3+9)=10
  humor: frequency=5 → effectiveness=min(10, 3+5)=8

Result:
knownHelpfulApproaches = [
  {
    "approach": "grounding",
    "effectiveness": 10,
    "frequency": 14,
    "lastUsed": "2026-05-22T10:30:00Z"
  },
  {
    "approach": "validation",
    "effectiveness": 10,
    "frequency": 9,
    "lastUsed": "2026-05-21T14:00:00Z"
  },
  {
    "approach": "humor",
    "effectiveness": 8,
    "frequency": 5,
    "lastUsed": "2026-05-20T09:15:00Z"
  }
]

           ↓

STEP 4: CALCULATE RISK BASELINE (PERCENTAGE-BASED)
──────────────────────────────────────────────────

Extract all riskTrend from sessions:
[
  "stable", "stable", "worsening",
  "stable", "worsening", "improving",
  "stable", "stable", "worsening",
  ...
]

Count occurrences:
{
  "stable": 12,
  "worsening": 6,
  "improving": 2,
  "volatile": 0
}

Determine overall trend:
  worsening_pct = 6 / 20 = 30%

  if worsening_pct > 40% → trend = "declining"
  elif improving_pct > 40% → trend = "improving"
  elif volatile_pct > 30% → trend = "declining" (volatility = bad)
  else → trend = "stable"

Result: riskTrend = "stable"

**NEW: Percentage-based HIGH risk classification**

high_risk_keywords = ["suicidal", "self_harm", "hopelessness", "severe_isolation"]

Count sessions with recurring high-risk signals:
  Examine warning signals across sessions:
  Session 1: ["hopelessness"]
  Session 2: ["isolation", "hopelessness"]
  Session 5: ["hopelessness"]
  ...

  Sessions with ANY high_risk_keyword = 4 out of 20 = 20%

Classification (CORRECTED):
  if high_risk_session_pct >= 20%:  ← REQUIRES RECURRENCE, not just presence
    riskBaseline = "HIGH"
  elif worsening_pct > 40%:
    riskBaseline = "MODERATE"
  elif volatile_pct > 30%:
    riskBaseline = "MODERATE"
  else:
    riskBaseline = "LOW"

Example:
  ✗ BAD (old logic):
    "hopelessness" appears once in session 3
    riskBaseline = "HIGH"  ← FALSE POSITIVE! (normal sadness ≠ ongoing crisis)

  ✓ GOOD (new logic):
    "hopelessness" appears in 4/20 sessions (20%)
    "self_harm" appears in 2/20 sessions (10%)
    4 + 2 = 6/20 = 30% ≥ 20%
    riskBaseline = "HIGH"  ← JUSTIFIED (recurring pattern)

Result: riskBaseline = "LOW"  (no high-risk keywords in ≥20% of sessions)

           ↓

STEP 5: CALCULATE STATS
───────────────────────

Total messages = sum of messageCount across sessions = 450
Total conversations = 20
Average risk level = mean of lastRiskLevel = 5.2

stats = {
  "totalConversations": 20,
  "totalMessages": 450,
  "averageRiskLevel": 5.2
}

           ↓

FINAL USER PROFILE
──────────────────

{
  "userId": "507f1f77bcf86cd799439011",
  "recurringThemes": [
    {
      "theme": "perfectionism",
      "frequency": 12,
      "embedding": [...],
      "lastSeen": "2026-05-22T10:30:00Z",
      "trend": "stable"
    },
    ...
  ],
  "commonTriggers": [
    {
      "trigger": "isolation_increasing",
      "frequency": 3,
      "embedding": [...]
    },
    ...
  ],
  "knownHelpfulApproaches": [
    {
      "approach": "grounding",
      "effectiveness": 10,
      "frequency": 14,
      "lastUsed": "2026-05-22T10:30:00Z"
    },
    ...
  ],
  "riskBaseline": "MODERATE",
  "riskTrend": "stable",
  "preferredSupportStyle": [],  # TODO: infer from patterns
  "lastProfileUpdate": "2026-05-22T10:45:00Z",
  "totalSessionsAnalyzed": 20,
  "stats": {
    "totalConversations": 20,
    "totalMessages": 450,
    "averageRiskLevel": 5.2
  }
}
```

### Why NO LLM?

```
If we used LLM:
- Cost: $0.01 per aggregation
- Latency: 3-5 seconds
- Non-deterministic (might give different results each time)
- Overkill for what's essentially counting + sorting

Statistical approach:
- Cost: ~$0.00001
- Latency: <100ms
- Deterministic (same input = same output)
- More trustworthy for analytics
```

---

## 4. LONGITUDINAL MEMORY COORDINATOR - Orchestration

### What It Does

Manages the UPDATE INTERVALS and decides WHEN to call each manager.

### Message Counter Logic

```python
# Track per conversation
_message_counters = {
  "userId_1_convId_1": 0,
  "userId_1_convId_2": 0,
  "userId_2_convId_5": 0,
}

# Each new message:
conv_key = f"{user_id}_{conversation_id}"
_message_counters[conv_key] += 1

# Check triggers:
if _message_counters[conv_key] >= 5 OR risk_jump:
  → Update session state
  → Reset counter to 0
```

### Profile Update Counter Logic

```python
# Track per user
_profile_update_counters = {
  "userId_1": 0,
  "userId_2": 0,
}

# After each session state update:
_profile_update_counters[user_id] += 1

# Check conditions:
if _profile_update_counters[user_id] >= 5:  # ← CHANGED: 10 → 5
  → Aggregate into profile
  → Reset counter to 0
else if time_since_last_update > 24_hours:
  → Aggregate into profile
  → Reset counter to 0
```

### Example Timeline

```
TIME    MESSAGE #   ACTION
────────────────────────────────────────────────────────
10:00   1          msg_count=1, no action
10:02   2          msg_count=2, no action
10:04   3          msg_count=3, no action
10:06   4          msg_count=4, no action
10:08   5          msg_count=5 → UPDATE SESSION STATE ✓
                   msg_count=0 (reset)
                   profile_counter=1
10:10   6          msg_count=1, no action
10:12   7          msg_count=2, no action
[... repeats 3 more times ...]
10:26   20         msg_count=5 → UPDATE SESSION STATE ✓
                   msg_count=0
                   profile_counter=2
[... repeats 3 more times ...]
11:05   50         msg_count=5 → UPDATE SESSION STATE ✓
                   msg_count=0
                   profile_counter=5 → UPDATE USER PROFILE ✓
                   profile_counter=0 (reset)

10:30   (risk spike)  Risk: 2 → 8
                   → Immediate SESSION STATE update (not waiting for 5)
```

---

## 5. DATABASE CLIENT - Persistence

### HTTP API vs Direct MongoDB

```
Approach 1: HTTP API (use if Node backend is separate)
────────────────────────────────────────────────────

Python → HTTP POST → Node.js → MongoDB
         (requests.post)

Example:
requests.post(
  "http://localhost:5000/api/session-state/update",
  json={
    "userId": "507f...",
    "conversationId": "conv_123",
    "riskTrend": "improving",
    ...
  }
)

Approach 2: Direct MongoDB (use if Python can access DB)
───────────────────────────────────────────────────────

Python → PyMongo → MongoDB

Example:
from pymongo import MongoClient
client = MongoClient("mongodb://localhost:27017")
db = client.therapy
db.sessionstates.update_one(
  {"userId": user_id, "conversationId": conversation_id},
  {"$set": state_data},
  upsert=True
)
```

### Upsert Behavior

```
Upsert = UPDATE or INSERT

First call:
  SessionState(userId="user1", convId="conv1") doesn't exist
  → INSERT new document

Second call (same user + conv):
  SessionState(userId="user1", convId="conv1") exists
  → UPDATE existing document

Third call (new conv, same user):
  SessionState(userId="user1", convId="conv2") doesn't exist
  → INSERT new document
```

---

## 6. API ROUTES - HTTP Interface

### SessionStateRoutes

```
POST /api/session-state/update
  Request:
    {
      "userId": "507f...",
      "conversationId": "conv_123",
      "riskTrend": "improving",
      "activeThemes": ["burnout"],
      ...
    }
  Response:
    {
      "success": true,
      "sessionState": {...}
    }

GET /api/session-state/:userId/:conversationId
  Response:
    {
      "success": true,
      "sessionState": {
        "userId": "507f...",
        "riskTrend": "improving",
        ...
      }
    }

GET /api/session-state/user/:userId?limit=10
  Response:
    {
      "success": true,
      "sessionStates": [
        {..}, {...}, ...
      ]
    }
```

### UserProfileRoutes

```
POST /api/user-profile/update
  Request:
    {
      "userId": "507f...",
      "riskBaseline": "MODERATE",
      "recurringThemes": [...],
      ...
    }

GET /api/user-profile/:userId
  Response:
    {
      "success": true,
      "userProfile": {
        "riskBaseline": "MODERATE",
        "recurringThemes": [...],
        ...
      }
    }

GET /api/user-profile/:userId/analysis
  Response:
    {
      "success": true,
      "analysis": {
        "riskLevel": "MODERATE",
        "topThemes": [
          {"theme": "perfectionism", "frequency": 12},
          ...
        ],
        "helpfulApproaches": [
          {"approach": "grounding", "effectiveness": 10},
          ...
        ]
      }
    }
```

---

## System Data Integrity

### What Happens If Components Fail?

```
1. SessionStateManager LLM fails
   ├─ Catches exception
   ├─ Falls back to neutral state
   └─ Conversation continues (no crash)

2. Database save fails
   ├─ Catches exception
   ├─ Logs error
   └─ Conversation continues (state not persisted, but OK)

3. Theme deduplication embedding fails
   ├─ Catches exception
   ├─ Keeps theme as separate entry
   └─ Profile slightly less clean, but valid

4. Profile aggregation has no sessions
   ├─ Skips aggregation
   └─ Old profile remains (safe default)
```

### Cascade: Message → Session → Profile

```
Single user message
      ↓
Triggers session state check (every 5 msgs)
      ↓
IF updates session state:
      ↓
Triggers profile update check (every 5 sessions)
      ↓
IF updates profile:
      ↓
Profile now reflects latest 20 sessions of activity
```

---

## Efficiency Analysis

### Computational Costs

```
Per message (~5 seconds):
  - Emotion detection: ~500ms
  - Risk assessment: ~200ms
  - RAG retrieval: ~1000ms
  - Strategy selection: ~300ms
  - Longitudinal check: ~0ms (just counter increment)

Per session state update (every 5 messages, ~30 seconds):
  - LLM extraction: ~2000ms (gemini-2.5-flash-lite)
  - Database save: ~50ms
  - Total overhead: ~2 seconds

Per profile update (every 5 sessions, ~2-3 minutes):
  - Fetch recent session states: ~50ms
  - Deduplicate themes: ~100ms (embeddings already computed)
  - Aggregate stats: ~50ms
  - Database save: ~50ms
  - Total overhead: <300ms (negligible)
```

### Storage Costs

```
Per SessionState doc: ~500 bytes
  - 20 conversations active = ~10 KB per user per day

Per UserProfile doc: ~2 KB
  - 1 per user = ~2 KB per user total

Monthly storage for 1000 users:
  - SessionStates: ~1000 × 10 KB × 30 = ~300 MB
  - UserProfiles: ~1000 × 2 KB = ~2 MB
  - Total: ~302 MB (negligible)
```

---

## Summary: How It All Connects

```
agent_stream.py
    │
    ├─ [After streaming response]
    │
    ├─ await coordinator.maybe_update_session_state()
    │   │
    │   ├─ Increment message counter
    │   │
    │   ├─ If counter >= 5:
    │   │  └─ SessionStateManager.update_session_state()
    │   │     ├─ LLM extracts: themes, risk_trend, warnings, helpers
    │   │     ├─ Database saves SessionState
    │   │     └─ Increment profile_update_counter
    │   │
    │   └─ If profile_counter >= 10:
    │      └─ UserProfileManager.aggregate_sessions_into_profile()
    │         ├─ Fetch 20 SessionStates
    │         ├─ ThemeDeduplicator clusters similar themes
    │         ├─ Calculate stats (frequency, effectiveness, trend)
    │         └─ Database saves UserProfile
    │
    └─ Response continues to frontend (no user-facing change)
```

---

This is the complete mental model of how the system works. Each component is independent but connected via the coordinator, and failures in one don't cascade to break the rest.
