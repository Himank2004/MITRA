const express = require("express");
const router = express.Router();
const SessionState = require("../models/SessionState");
const UserProfile = require("../models/UserProfile");
const { ObjectId } = require("mongoose");
const { protect } = require("../middleware/authMiddleware");
const { normalizeUserId } = require("../utils/idNormalizer");

/**
 * POST /api/session-state/update
 * Update or create session state
 * Auth: Required
 */
router.post("/update", protect, async (req, res) => {
    try {
        const {
            userId,
            conversationId,
            riskTrend,
            activeThemes,
            activeWarningSignals,
            whatHelpedThisSession,
            messageCount,
            lastDetectedEmotions,
            lastRiskLevel,
            lastRiskConfidence,
        } = req.body;

        if (!userId || !conversationId) {
            return res
                .status(400)
                .json({ error: "Missing userId or conversationId" });
        }

        // Normalize userId to handle both string and ObjectId formats
        const normalizedUserId = normalizeUserId(userId);

        const updated = await SessionState.findOneAndUpdate(
            { userId: normalizedUserId, conversationId },
            {
                riskTrend,
                activeThemes,
                activeWarningSignals,
                whatHelpedThisSession,
                messageCount,
                lastDetectedEmotions,
                lastRiskLevel,
                lastRiskConfidence,
            },
            { upsert: true, new: true },
        );

        return res.json({ success: true, sessionState: updated });
    } catch (error) {
        console.error("[SessionState] Error:", error);
        return res.status(500).json({ error: error.message });
    }
});

/**
 * GET /api/session-state/user
 * Get recent session states for authenticated user
 * Auth: Required
 */
router.get("/user", protect, async (req, res) => {
    try {
        // Get userId from authenticated request
        const userId = normalizeUserId(req.user._id);
        const limit = req.query.limit || 100;

        const sessionStates = await SessionState.find({ userId })
            .sort({ createdAt: -1 })
            .limit(parseInt(limit));

        return res.json(sessionStates);
    } catch (error) {
        console.error("[SessionState] Error:", error);
        return res.status(500).json({ error: error.message });
    }
});

/**
 * GET /api/session-state/:userId/:conversationId
 * Retrieve session state for specific conversation
 * Auth: Required (must be the user's own data)
 */
router.get("/:userId/:conversationId", protect, async (req, res) => {
    try {
        const { userId, conversationId } = req.params;

        // Security: ensure user can only access their own session states
        const normalizedReqUserId = normalizeUserId(req.user._id);
        const normalizedParamUserId = normalizeUserId(userId);
        
        if (normalizedReqUserId !== normalizedParamUserId) {
            return res.status(403).json({ error: "Unauthorized" });
        }

        const sessionState = await SessionState.findOne({
            userId: normalizedParamUserId,
            conversationId,
        });

        if (!sessionState) {
            return res.status(404).json({ error: "Session state not found" });
        }

        return res.json({ success: true, sessionState });
    } catch (error) {
        console.error("[SessionState] Error:", error);
        return res.status(500).json({ error: error.message });
    }
});

module.exports = router;
