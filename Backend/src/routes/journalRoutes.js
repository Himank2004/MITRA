const express = require("express");
const {
    getJournals,
    createJournal,
    updateJournal,
    deleteJournal,
    linkReflection,
} = require("../controllers/journalController");
const { protect } = require("../middleware/authMiddleware");

const router = express.Router();

router.route("/").get(protect, getJournals).post(protect, createJournal);
router.route("/:id").put(protect, updateJournal).delete(protect, deleteJournal);
router.route("/:id/reflection").patch(protect, linkReflection);

module.exports = router;
