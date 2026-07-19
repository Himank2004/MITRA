const Journal = require("../models/Journal");
const Task = require("../models/Task");
const { normalizeUserId } = require("../utils/idNormalizer");

// @desc    Get all journal entries for user
// @route   GET /api/journals
// @access  Private
const getJournals = async (req, res) => {
    try {
        const userId = normalizeUserId(req.user._id);
        const journals = await Journal.find({ userId })
            .sort({ createdAt: -1 })
            .lean();
        res.json(journals);
    } catch (err) {
        res.status(500).json({ message: err.message });
    }
};

// @desc    Create a journal entry
// @route   POST /api/journals
// @access  Private
const createJournal = async (req, res) => {
    try {
        const { title, content, taskId } = req.body;
        if (!content || !content.trim()) {
            return res.status(400).json({ message: "Content is required" });
        }

        const userId = normalizeUserId(req.user._id);
        const journal = await Journal.create({
            userId,
            title: title || "",
            content,
            taskId: taskId || null,
        });

        // If linked to a task, mark it complete via progress=1
        if (taskId) {
            const task = await Task.findOne({
                _id: taskId,
                userId,
            });
            if (task) {
                const now = new Date();
                task.progress = 1;
                task.completed = true;
                task.completedAt = now;
                if (task.recurringHours > 0) {
                    task.nextDueAt = new Date(
                        now.getTime() + task.recurringHours * 3600 * 1000,
                    );
                }
                await task.save();
            }
        }

        res.status(201).json(journal);
    } catch (err) {
        res.status(500).json({ message: err.message });
    }
};

// @desc    Update a journal entry
// @route   PUT /api/journals/:id
// @access  Private
const updateJournal = async (req, res) => {
    try {
        const { title, content } = req.body;
        const userId = normalizeUserId(req.user._id);
        const journal = await Journal.findOneAndUpdate(
            { _id: req.params.id, userId },
            { title, content },
            { new: true, runValidators: true },
        );
        if (!journal)
            return res.status(404).json({ message: "Journal not found" });
        res.json(journal);
    } catch (err) {
        res.status(500).json({ message: err.message });
    }
};

// @desc    Delete a journal entry
// @route   DELETE /api/journals/:id
// @access  Private
const deleteJournal = async (req, res) => {
    try {
        const userId = normalizeUserId(req.user._id);
        const journal = await Journal.findOneAndDelete({
            _id: req.params.id,
            userId,
        });
        if (!journal)
            return res.status(404).json({ message: "Journal not found" });
        res.json({ message: "Journal deleted" });
    } catch (err) {
        res.status(500).json({ message: err.message });
    }
};

// @desc    Link (or clear) a reflection conversation to a journal entry
// @route   PATCH /api/journals/:id/reflection
// @access  Private
const linkReflection = async (req, res) => {
    try {
        const { reflectionConversationId } = req.body;
        const userId = normalizeUserId(req.user._id);
        const journal = await Journal.findOneAndUpdate(
            { _id: req.params.id, userId },
            { reflectionConversationId: reflectionConversationId || null },
            { new: true },
        );
        if (!journal)
            return res.status(404).json({ message: "Journal not found" });
        res.json(journal);
    } catch (err) {
        res.status(500).json({ message: err.message });
    }
};

module.exports = {
    getJournals,
    createJournal,
    updateJournal,
    deleteJournal,
    linkReflection,
};
