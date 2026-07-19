const mongoose = require("mongoose");

/**
 * UserProfile: Long-term psychological continuity
 *
 * Updated periodically (not on every message) via aggregation from SessionStates.
 * Captures slow-changing patterns that persist across conversations.
 */
const userProfileSchema = mongoose.Schema(
    {
        userId: {
            type: String,  // Accept both string and ObjectId via normalizeUserId
            required: true,
            unique: true,
            index: true,
        },

        // Recurring themes seen across sessions
        recurringThemes: [
            {
                theme: String,
                frequency: Number, // times observed
                embedding: [Number], // all-mpnet-base-v2 (768-dim)
                lastSeen: Date,
                trend: {
                    type: String,
                    enum: ["improving", "stable", "worsening"],
                },
            },
        ],

        // Common triggers (events/situations that precede distress)
        commonTriggers: [
            {
                trigger: String,
                frequency: Number,
                embedding: [Number],
                lastSeen: Date,
            },
        ],

        // User's preferred communication/support style
        preferredSupportStyle: {
            type: [String],
            default: [],
            // e.g., ["slow_pacing", "few_questions", "direct_advice", "exploration"]
        },

        // Approaches consistently helpful for this user
        knownHelpfulApproaches: [
            {
                approach: String,
                effectiveness: Number, // 1-10 scale
                frequency: Number, // times tried
                lastUsed: Date,
            },
        ],

        // Overall baseline risk level (computed from risk history)
        riskBaseline: {
            type: String,
            enum: ["LOW", "MODERATE", "MODERATE-HIGH", "HIGH"],
            default: "LOW",
        },

        // Trend in risk over time
        riskTrend: {
            type: String,
            enum: ["improving", "stable", "declining"],
            default: "stable",
        },

        // Metadata for update scheduling
        lastProfileUpdate: Date,
        sessionsSinceLastUpdate: { type: Number, default: 0 },
        totalSessionsAnalyzed: { type: Number, default: 0 },

        // Summary stats
        stats: {
            totalConversations: { type: Number, default: 0 },
            totalMessages: { type: Number, default: 0 },
            averageRiskLevel: { type: Number, default: 0 },
        },
    },
    { timestamps: true },
);

const UserProfile = mongoose.model("UserProfile", userProfileSchema);
module.exports = UserProfile;
