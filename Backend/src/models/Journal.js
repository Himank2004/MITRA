const mongoose = require("mongoose");

const journalSchema = mongoose.Schema(
    {
        userId: {
            type: String,
            required: true,
            index: true,
        },
        title: {
            type: String,
            default: "",
        },
        content: {
            type: String,
            required: true,
        },
        // Linked task (only for journal-type tasks — marks task progress when saved)
        taskId: {
            type: mongoose.Schema.Types.ObjectId,
            ref: "Task",
            default: null,
        },
        // Optional semantic embedding (sentence-transformers/all-mpnet-base-v2, 768-dim)
        embedding: {
            type: [Number],
            default: undefined,
        },
        // Linked companion reflection conversation
        reflectionConversationId: {
            type: mongoose.Schema.Types.ObjectId,
            ref: "Conversation",
            default: null,
        },
    },
    { timestamps: true },
);

const Journal = mongoose.model("Journal", journalSchema);
module.exports = Journal;
