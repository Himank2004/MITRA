/**
 * Utility to normalize IDs between string and ObjectId formats
 * Allows queries to work with both formats seamlessly
 */

const { ObjectId } = require("mongoose");

/**
 * Normalize userId to work with both string and ObjectId
 * Converts ObjectId to string for consistent comparison
 * @param {string|ObjectId} userId - User ID in either format
 * @returns {string} - User ID as string
 */
function normalizeUserId(userId) {
    if (!userId) return userId;
    
    // If it's an ObjectId, convert to string
    if (userId instanceof ObjectId) {
        return userId.toString();
    }
    
    // If it's already a string, return as-is
    if (typeof userId === "string") {
        return userId;
    }
    
    return userId;
}

/**
 * Convert ID to ObjectId if valid, otherwise keep as string
 * Used when querying MongoDB with flexible ID format
 * @param {string|ObjectId} id - ID to convert
 * @returns {string|ObjectId} - ID in appropriate format
 */
function toObjectIdIfValid(id) {
    if (!id) return id;
    
    // Already an ObjectId
    if (id instanceof ObjectId) {
        return id;
    }
    
    // String that looks like ObjectId
    if (typeof id === "string" && ObjectId.isValid(id)) {
        try {
            return new ObjectId(id);
        } catch (e) {
            return id;
        }
    }
    
    return id;
}

/**
 * Build a flexible query that works with both string and ObjectId userIds
 * @param {string|ObjectId} userId - User ID in either format
 * @returns {object} - MongoDB query object
 */
function buildUserIdQuery(userId) {
    const normalized = normalizeUserId(userId);
    
    // Query that matches both string and ObjectId representations
    return {
        $or: [
            { userId: normalized },
            { userId: toObjectIdIfValid(normalized) }
        ]
    };
}

module.exports = {
    normalizeUserId,
    toObjectIdIfValid,
    buildUserIdQuery
};
