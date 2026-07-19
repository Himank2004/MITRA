const mongoose = require("mongoose");

/**
 * SessionState: Real-time conversation tracking
 *
 * Updated every ~5 messages or when risk dramatically shifts.
 * Captures the current "temperature" of a conversation.
 */
const sessionStateSchema = mongoose.Schema(
    {
        userId: {
            type: String,  // Accept both string and ObjectId via normalizeUserId
            required: true,
            index: true,
        },
        conversationId: {
            type: String,
            required: true,
            index: true,
        },

        // Risk trajectory within this conversation
        riskTrend: {
            type: String,
            enum: ["stable", "worsening", "improving", "volatile"],
            default: "stable",
        },

        // Active psychological themes in THIS conversation
        activeThemes: {
            type: [String],
            default: [],
        },

        // Active warning signals in THIS conversation
        activeWarningSignals: {
            type: [String],
            default: [],
        },

        // Techniques/approaches that worked THIS session
        whatHelpedThisSession: {
            type: [String],
            default: [],
        },

        // Tracking for update triggers
        messageCount: {
            type: Number,
            default: 0,
        },

        // Emotion snapshot at last update
        lastDetectedEmotions: [String],

        // Risk level snapshot (enum instead of numeric)
        lastRiskLevel: {
            type: String,
            enum: ["NONE", "LOW", "MODERATE", "HIGH", "IMMINENT"],
            default: "NONE",
        },
        lastRiskConfidence: Number,

        // Staleness metric: tracks how many consecutive LLM extraction failures
        // 0 = fresh (just extracted from LLM)
        // 1 = one update old (fallback from previous state)
        // 2+ = very stale (multiple consecutive failures)
        // Agent can use this to decide how much to trust the state
        staleness: {
            type: Number,
            default: 0,
        },
    },
    { timestamps: true },
);

// Index for efficient querying
sessionStateSchema.index({ userId: 1, conversationId: 1 });

const SessionState = mongoose.model("SessionState", sessionStateSchema);
module.exports = SessionState;
