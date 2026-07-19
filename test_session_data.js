// Test data insertion for SessionStates
// Run with: mongosh test_session_data.js

db = db.getSiblingDB("therapy");

// Find or create a test user
const testUserId = "test-user-001";
const testUserEmail = "testuser@example.com";

// Insert test user if doesn't exist
db.users.updateOne(
    { _id: testUserId },
    {
        $setOnInsert: {
            _id: testUserId,
            email: testUserEmail,
            username: "TestUser",
            passwordHash: "hash",
            interests: ["mental health", "wellness"],
            createdAt: new Date(),
        },
    },
    { upsert: true },
);

console.log("✓ Test user created/verified");

// Insert test SessionStates for conversation 1
db.sessionstates.insertMany([
    {
        userId: testUserId,
        conversationId: "conv-001",
        riskTrend: "improving",
        activeThemes: ["anxiety", "work-stress", "sleep-issues"],
        activeWarningSignals: ["worry", "fatigue"],
        whatHelpedThisSession: ["breathing exercises", "perspective shift"],
        messageCount: 12,
        lastDetectedEmotions: ["anxious", "tired", "hopeful"],
        lastRiskLevel: "MODERATE",
        lastRiskConfidence: 0.85,
        staleness: 0,
        createdAt: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000), // 7 days ago
    },
    {
        userId: testUserId,
        conversationId: "conv-001",
        riskTrend: "stable",
        activeThemes: ["anxiety", "work-stress"],
        activeWarningSignals: ["worry"],
        whatHelpedThisSession: ["cognitive reframing", "mindfulness"],
        messageCount: 8,
        lastDetectedEmotions: ["anxious", "calm"],
        lastRiskLevel: "LOW",
        lastRiskConfidence: 0.82,
        staleness: 0,
        createdAt: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000), // 3 days ago
    },
]);

console.log("✓ SessionStates for conv-001 inserted");

// Insert test SessionStates for conversation 2
db.sessionstates.insertMany([
    {
        userId: testUserId,
        conversationId: "conv-002",
        riskTrend: "declining",
        activeThemes: ["relationship-conflict", "communication"],
        activeWarningSignals: ["anger", "frustration", "hopelessness"],
        whatHelpedThisSession: ["validation", "listening"],
        messageCount: 15,
        lastDetectedEmotions: ["frustrated", "heard"],
        lastRiskLevel: "MODERATE-HIGH",
        lastRiskConfidence: 0.88,
        staleness: 0,
        createdAt: new Date(Date.now() - 5 * 24 * 60 * 60 * 1000), // 5 days ago
    },
    {
        userId: testUserId,
        conversationId: "conv-002",
        riskTrend: "stable",
        activeThemes: ["relationship-conflict"],
        activeWarningSignals: ["frustration"],
        whatHelpedThisSession: ["boundaries talk"],
        messageCount: 10,
        lastDetectedEmotions: ["thoughtful", "calm"],
        lastRiskLevel: "MODERATE",
        lastRiskConfidence: 0.8,
        staleness: 0,
        createdAt: new Date(Date.now() - 1 * 24 * 60 * 60 * 1000), // 1 day ago
    },
]);

console.log("✓ SessionStates for conv-002 inserted");

// Insert test SessionStates for conversation 3
db.sessionstates.insertMany([
    {
        userId: testUserId,
        conversationId: "conv-003",
        riskTrend: "improving",
        activeThemes: ["self-esteem", "perfectionism"],
        activeWarningSignals: ["self-criticism"],
        whatHelpedThisSession: ["self-compassion", "reframing"],
        messageCount: 11,
        lastDetectedEmotions: ["insecure", "hopeful"],
        lastRiskLevel: "LOW",
        lastRiskConfidence: 0.75,
        staleness: 0,
        createdAt: new Date(), // today
    },
]);

console.log("✓ SessionStates for conv-003 inserted");

// Insert a test UserProfile
db.userprofiles.updateOne(
    { userId: testUserId },
    {
        $set: {
            userId: testUserId,
            recurringThemes: [
                { name: "anxiety", frequency: 3, embedding: [] },
                { name: "work-stress", frequency: 2, embedding: [] },
                { name: "relationship-conflict", frequency: 2, embedding: [] },
                { name: "self-esteem", frequency: 1, embedding: [] },
            ],
            commonTriggers: [
                { signal: "worry", frequency: 3 },
                { signal: "frustration", frequency: 2 },
                { signal: "self-criticism", frequency: 1 },
            ],
            knownHelpfulApproaches: [
                { name: "breathing exercises", effectiveness: 8 },
                { name: "cognitive reframing", effectiveness: 7 },
                { name: "mindfulness", effectiveness: 7 },
                { name: "validation", effectiveness: 8 },
            ],
            riskBaseline: "MODERATE",
            riskTrend: "improving",
            lastProfileUpdate: new Date(),
            sessionsSinceLastUpdate: 0,
            totalSessionsAnalyzed: 5,
            stats: {
                avgRiskLevel: 1.7, // Average of: MODERATE(2) + LOW(1) + MODERATE-HIGH(2.5) + MODERATE(2) + LOW(1)
                sessionsAnalyzed: 5,
            },
        },
    },
    { upsert: true },
);

console.log("✓ UserProfile inserted");

console.log("\n✅ All test data inserted successfully!");
console.log(`Test User ID: ${testUserId}`);
console.log("Available conversations: conv-001, conv-002, conv-003");
