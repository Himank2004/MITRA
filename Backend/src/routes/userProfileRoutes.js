const express = require("express");
const router = express.Router();
const UserProfile = require("../models/UserProfile");
const { normalizeUserId } = require("../utils/idNormalizer");

/**
 * POST /api/user-profile/update
 * Update or create user profile
 */
router.post("/update", async (req, res) => {
    try {
        const {
            userId,
            recurringThemes,
            commonTriggers,
            preferredSupportStyle,
            knownHelpfulApproaches,
            riskBaseline,
            riskTrend,
            lastProfileUpdate,
            sessionsSinceLastUpdate,
            totalSessionsAnalyzed,
            stats,
        } = req.body;

        if (!userId) {
            return res.status(400).json({ error: "Missing userId" });
        }

        // Normalize userId to string
        const normalizedUserId = normalizeUserId(userId);

        const updated = await UserProfile.findOneAndUpdate(
            { userId: normalizedUserId },
            {
                recurringThemes,
                commonTriggers,
                preferredSupportStyle,
                knownHelpfulApproaches,
                riskBaseline,
                riskTrend,
                lastProfileUpdate,
                sessionsSinceLastUpdate,
                totalSessionsAnalyzed,
                stats,
            },
            { upsert: true, new: true },
        );

        return res.json({ success: true, userProfile: updated });
    } catch (error) {
        console.error("[UserProfile] Error:", error);
        return res.status(500).json({ error: error.message });
    }
});

/**
 * GET /api/user-profile/:userId
 * Retrieve user profile
 */
router.get("/:userId", async (req, res) => {
    try {
        const { userId } = req.params;

        // Normalize userId to string
        const normalizedUserId = normalizeUserId(userId);

        const userProfile = await UserProfile.findOne({
            userId: normalizedUserId,
        });

        if (!userProfile) {
            return res.status(404).json({ error: "User profile not found" });
        }

        return res.json(userProfile);
    } catch (error) {
        console.error("[UserProfile] Error:", error);
        return res.status(500).json({ error: error.message });
    }
});

/**
 * GET /api/user-profile/:userId/analysis
 * Get analysis/summary of user profile
 */
router.get("/:userId/analysis", async (req, res) => {
    try {
        const { userId } = req.params;

        // Normalize userId to string
        const normalizedUserId = normalizeUserId(userId);

        const userProfile = await UserProfile.findOne({
            userId: normalizedUserId,
        });

        if (!userProfile) {
            return res.status(404).json({ error: "User profile not found" });
        }

        // Return analysis summary
        return res.json({
            success: true,
            analysis: {
                riskLevel: userProfile.riskBaseline,
                riskTrend: userProfile.riskTrend,
                topThemes: userProfile.recurringThemes.slice(0, 3).map((t) => ({
                    theme: t.theme,
                    frequency: t.frequency,
                })),
                topTriggers: userProfile.commonTriggers
                    .slice(0, 3)
                    .map((t) => ({
                        trigger: t.trigger,
                        frequency: t.frequency,
                    })),
                helpfulApproaches: userProfile.knownHelpfulApproaches
                    .slice(0, 3)
                    .map((a) => ({
                        approach: a.approach,
                        effectiveness: a.effectiveness,
                    })),
                supportPreferences: userProfile.preferredSupportStyle,
                lastUpdated: userProfile.lastProfileUpdate,
            },
        });
    } catch (error) {
        console.error("[UserProfile] Error:", error);
        return res.status(500).json({ error: error.message });
    }
});

module.exports = router;
