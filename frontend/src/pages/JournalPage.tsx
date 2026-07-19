import React, { useState, useEffect, useCallback } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import Header from "../components/Header";

const BACKEND_URL =
    process.env.REACT_APP_BACKEND_URL || "http://localhost:3000";
const ML_API_URL = process.env.REACT_APP_API_URL || "http://localhost:5000";

interface Journal {
    _id: string;
    title: string;
    content: string;
    taskId?: string;
    createdAt: string;
    reflectionConversationId?: string | null;
}

function getAuth() {
    try {
        const raw = localStorage.getItem("user");
        if (!raw) return { token: "" };
        return { token: (JSON.parse(raw).token as string) || "" };
    } catch {
        return { token: "" };
    }
}

const JournalPage: React.FC = () => {
    const { token } = getAuth();
    const location = useLocation();
    const navigate = useNavigate();
    const queryTaskId =
        new URLSearchParams(location.search).get("taskId") || "";

    const authHeaders = {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
    };

    const [journals, setJournals] = useState<Journal[]>([]);
    const [loading, setLoading] = useState(true);

    // Editor state
    const [editorOpen, setEditorOpen] = useState(!!queryTaskId);
    const [editId, setEditId] = useState<string | null>(null);
    const [title, setTitle] = useState("");
    const [content, setContent] = useState("");
    const [activeTaskId, setActiveTaskId] = useState(queryTaskId);
    const [saving, setSaving] = useState(false);
    const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
    const [reflecting, setReflecting] = useState<string | null>(null); // journal id being reflected

    const fetchJournals = useCallback(async () => {
        if (!token) {
            setLoading(false);
            return;
        }
        try {
            const res = await fetch(`${BACKEND_URL}/api/journals`, {
                headers: authHeaders,
            });
            if (res.ok) setJournals(await res.json());
        } finally {
            setLoading(false);
        }
    }, [token]); // eslint-disable-line react-hooks/exhaustive-deps

    useEffect(() => {
        fetchJournals();
    }, [fetchJournals]);

    // Auto-populate title when opened from a task link
    useEffect(() => {
        if (!queryTaskId || !token) return;
        const pad = (n: number) => String(n).padStart(2, "0");
        const now = new Date();
        const dateStr = `${pad(now.getMonth() + 1)}/${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}`;
        (async () => {
            try {
                const res = await fetch(`${BACKEND_URL}/api/tasks`, {
                    headers: authHeaders,
                });
                if (res.ok) {
                    const tasks: { _id: string; taskName: string }[] =
                        await res.json();
                    const matched = tasks.find((t) => t._id === queryTaskId);
                    if (matched) {
                        setTitle(`${matched.taskName} - ${dateStr}`);
                    }
                }
            } catch {
                // silently ignore — title stays empty
            }
        })();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [queryTaskId]);

    const openNew = () => {
        setEditId(null);
        setTitle("");
        setContent("");
        setActiveTaskId(queryTaskId);
        setEditorOpen(true);
    };

    const openEdit = (j: Journal) => {
        setEditId(j._id);
        setTitle(j.title || "");
        setContent(j.content);
        setActiveTaskId(j.taskId || "");
        setEditorOpen(true);
    };

    const closeEditor = () => {
        setEditorOpen(false);
        setEditId(null);
        setTitle("");
        setContent("");
    };

    const handleSave = async (markDone: boolean) => {
        if (!content.trim()) return;
        setSaving(true);
        try {
            if (editId) {
                // Update existing
                const res = await fetch(
                    `${BACKEND_URL}/api/journals/${editId}`,
                    {
                        method: "PUT",
                        headers: authHeaders,
                        body: JSON.stringify({ title, content }),
                    },
                );
                if (res.ok) {
                    const updated: Journal = await res.json();
                    setJournals((j) =>
                        j.map((x) => (x._id === updated._id ? updated : x)),
                    );
                    // If marking done, call task progress endpoint
                    if (markDone && activeTaskId) {
                        await fetch(
                            `${BACKEND_URL}/api/tasks/${activeTaskId}/progress`,
                            {
                                method: "PUT",
                                headers: authHeaders,
                                body: JSON.stringify({ progress: 1 }),
                            },
                        );
                    }
                }
            } else {
                // Create new — passing taskId will auto-mark the task complete in the controller
                const res = await fetch(`${BACKEND_URL}/api/journals`, {
                    method: "POST",
                    headers: authHeaders,
                    body: JSON.stringify({
                        title,
                        content,
                        taskId:
                            markDone && activeTaskId ? activeTaskId : undefined,
                    }),
                });
                if (res.ok) {
                    const created: Journal = await res.json();
                    setJournals((j) => [created, ...j]);
                }
            }

            closeEditor();
            if (markDone && activeTaskId) navigate("/tasks");
        } finally {
            setSaving(false);
        }
    };

    const handleDelete = async (id: string) => {
        const res = await fetch(`${BACKEND_URL}/api/journals/${id}`, {
            method: "DELETE",
            headers: authHeaders,
        });
        if (res.ok) {
            setJournals((j) => j.filter((x) => x._id !== id));
            if (editId === id) closeEditor();
        }
        setDeleteConfirm(null);
    };

    const handleReflect = async (j: Journal) => {
        // Already has a reflection conversation — just navigate
        if (j.reflectionConversationId) {
            navigate(`/pet?conversationId=${j.reflectionConversationId}`);
            return;
        }

        setReflecting(j._id);
        try {
            // 1. Fetch linked task name (if any) for context
            let taskContext = "";
            if (j.taskId) {
                try {
                    const taskRes = await fetch(`${BACKEND_URL}/api/tasks`, {
                        headers: authHeaders,
                    });
                    if (taskRes.ok) {
                        const tasks: {
                            _id: string;
                            taskName: string;
                            description?: string;
                        }[] = await taskRes.json();
                        const matched = tasks.find((t) => t._id === j.taskId);
                        if (matched) {
                            taskContext = `Task: ${matched.taskName}${matched.description ? ` — ${matched.description}` : ""}`;
                        }
                    }
                } catch {
                    // ignore
                }
            }

            // 2. Create conversation in Node.js backend
            const convTitle = `Reflection on ${j.title || j.content.slice(0, 40) || "Journal Entry"}`;
            const convRes = await fetch(`${BACKEND_URL}/api/conversations`, {
                method: "POST",
                headers: authHeaders,
                body: JSON.stringify({ title: convTitle }),
            });
            if (!convRes.ok) throw new Error("Failed to create conversation");
            const conv = await convRes.json();
            const convId: string = conv._id;

            // 3. Seed the conversation via ML Backend (consume full SSE stream)
            const mlRes = await fetch(`${ML_API_URL}/chat/journal`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    journalTitle: j.title || "",
                    journalContent: j.content,
                    conversationId: convId,
                    userId:
                        (
                            JSON.parse(
                                localStorage.getItem("user") || "{}",
                            ) as { _id?: string }
                        )._id || "",
                    taskContext,
                }),
            });
            if (mlRes.ok && mlRes.body) {
                const reader = mlRes.body.getReader();
                // Consume the full stream so the server saves the turn to DB
                while (true) {
                    const { done } = await reader.read();
                    if (done) break;
                }
            }

            // 4. Brief pause for the background DB save thread to complete
            await new Promise((r) => setTimeout(r, 600));

            // 5. Save reflectionConversationId on the journal
            const patchRes = await fetch(
                `${BACKEND_URL}/api/journals/${j._id}/reflection`,
                {
                    method: "PATCH",
                    headers: authHeaders,
                    body: JSON.stringify({ reflectionConversationId: convId }),
                },
            );
            if (patchRes.ok) {
                const updated: Journal = await patchRes.json();
                setJournals((prev) =>
                    prev.map((x) => (x._id === updated._id ? updated : x)),
                );
            }

            // 6. Navigate to the companion page
            navigate(`/pet?conversationId=${convId}`);
        } catch (err) {
            console.error("Reflect error", err);
        } finally {
            setReflecting(null);
        }
    };

    const dateStr = (iso: string) =>
        new Date(iso).toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
            year: "numeric",
        });

    return (
        <div className="min-h-screen bg-[#F9FAFB]">
            <Header />
            <main className="max-w-2xl mx-auto px-4 py-10">
                {/* Page header */}
                <div className="mb-6 flex items-center justify-between">
                    <div>
                        <h1 className="text-2xl font-bold text-[#1F2937]">
                            Journal
                        </h1>
                        {queryTaskId && (
                            <p className="text-xs text-purple-600 mt-0.5 font-medium">
                                ✏️ Writing for a task — use "Save &amp; Mark
                                Done" to complete it
                            </p>
                        )}
                    </div>
                    <button
                        onClick={openNew}
                        className="px-4 py-2 rounded-lg bg-[#C66408] text-white text-sm font-semibold hover:bg-[#B35C07] transition-colors"
                    >
                        + New Entry
                    </button>
                </div>

                {/* Inline editor */}
                {editorOpen && (
                    <div className="bg-white rounded-xl shadow-md border border-gray-100 mb-6 overflow-hidden">
                        <div className="p-4 border-b border-gray-100">
                            <input
                                type="text"
                                placeholder="Title (optional)"
                                value={title}
                                onChange={(e) => setTitle(e.target.value)}
                                className="w-full text-base font-semibold text-[#1F2937] placeholder:text-gray-300 focus:outline-none"
                            />
                        </div>
                        <textarea
                            value={content}
                            onChange={(e) => setContent(e.target.value)}
                            placeholder="Write freely… this is your private space."
                            rows={12}
                            className="w-full p-4 text-sm text-[#1F2937] leading-relaxed resize-none focus:outline-none placeholder:text-[#9CA3AF]"
                            autoFocus
                        />
                        <div className="border-t border-gray-100 px-4 py-3 flex items-center justify-between gap-2 flex-wrap">
                            <span className="text-xs text-[#9CA3AF]">
                                {content.length} characters
                            </span>
                            <div className="flex gap-2 flex-wrap">
                                <button
                                    onClick={closeEditor}
                                    className="px-3 py-1.5 rounded-lg border text-sm text-gray-500 hover:bg-gray-50 transition-colors"
                                >
                                    Cancel
                                </button>
                                {activeTaskId && (
                                    <button
                                        onClick={() => handleSave(true)}
                                        disabled={saving || !content.trim()}
                                        className="px-4 py-1.5 rounded-lg bg-green-600 text-white text-sm font-semibold hover:bg-green-700 disabled:opacity-40 transition-colors"
                                    >
                                        {saving
                                            ? "Saving…"
                                            : "Save & Mark Done ✓"}
                                    </button>
                                )}
                                <button
                                    onClick={() => handleSave(false)}
                                    disabled={saving || !content.trim()}
                                    className="px-4 py-1.5 rounded-lg bg-[#C66408] text-white text-sm font-semibold hover:bg-[#B35C07] disabled:opacity-40 transition-colors"
                                >
                                    {saving ? "Saving…" : "Save"}
                                </button>
                            </div>
                        </div>
                    </div>
                )}

                {/* Journal list */}
                {loading ? (
                    <div className="text-center py-16 text-[#9CA3AF] text-sm">
                        Loading…
                    </div>
                ) : journals.length === 0 && !editorOpen ? (
                    <div className="text-center py-16">
                        <p className="text-[#9CA3AF] text-sm">
                            No journal entries yet.
                        </p>
                        <button
                            onClick={openNew}
                            className="mt-3 text-sm text-[#C66408] underline"
                        >
                            Write your first entry
                        </button>
                    </div>
                ) : (
                    <div className="space-y-3">
                        {journals.map((j) => (
                            <div
                                key={j._id}
                                className="bg-white rounded-xl border border-gray-100 shadow-sm p-4 hover:shadow-md transition-shadow"
                            >
                                <div className="flex items-start justify-between gap-2">
                                    {/* Clickable preview */}
                                    <div
                                        className="flex-1 min-w-0 cursor-pointer"
                                        onClick={() => openEdit(j)}
                                    >
                                        <p className="text-sm font-semibold text-[#1F2937] truncate">
                                            {j.title ||
                                                j.content.slice(0, 60) ||
                                                "Untitled"}
                                        </p>
                                        {j.title && (
                                            <p className="text-xs text-[#6B7280] mt-0.5 line-clamp-2">
                                                {j.content.slice(0, 100)}
                                            </p>
                                        )}
                                        <div className="flex items-center gap-2 mt-1">
                                            <p className="text-[10px] text-[#9CA3AF]">
                                                {dateStr(j.createdAt)}
                                            </p>
                                            {j.taskId && (
                                                <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-purple-100 text-purple-600 font-medium">
                                                    linked to task
                                                </span>
                                            )}
                                            {j.reflectionConversationId && (
                                                <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-violet-100 text-violet-600 font-medium">
                                                    reflection saved
                                                </span>
                                            )}
                                        </div>
                                    </div>

                                    {/* Actions */}
                                    <div className="flex items-center gap-1 flex-shrink-0">
                                        {/* Discuss with companion */}
                                        <button
                                            onClick={() => handleReflect(j)}
                                            disabled={reflecting === j._id}
                                            title={
                                                j.reflectionConversationId
                                                    ? "Open reflection conversation"
                                                    : "Discuss with companion"
                                            }
                                            className={`text-xs px-2 py-1 rounded transition-colors ${
                                                j.reflectionConversationId
                                                    ? "text-violet-500 hover:bg-violet-50"
                                                    : "text-[#C66408] hover:bg-orange-50"
                                            } disabled:opacity-40`}
                                        >
                                            {reflecting === j._id
                                                ? "Starting…"
                                                : j.reflectionConversationId
                                                  ? "💬 Reflect"
                                                  : "💬 Discuss"}
                                        </button>
                                        <button
                                            onClick={() => openEdit(j)}
                                            className="text-xs px-2 py-1 rounded text-gray-400 hover:text-[#C66408] hover:bg-orange-50 transition-colors"
                                        >
                                            Edit
                                        </button>
                                        {deleteConfirm === j._id ? (
                                            <>
                                                <button
                                                    onClick={() =>
                                                        handleDelete(j._id)
                                                    }
                                                    className="text-xs px-2 py-1 rounded bg-red-100 text-red-600 hover:bg-red-200 transition-colors"
                                                >
                                                    Confirm
                                                </button>
                                                <button
                                                    onClick={() =>
                                                        setDeleteConfirm(null)
                                                    }
                                                    className="text-xs px-2 py-1 rounded text-gray-400 hover:bg-gray-50 transition-colors"
                                                >
                                                    ✕
                                                </button>
                                            </>
                                        ) : (
                                            <button
                                                onClick={() =>
                                                    setDeleteConfirm(j._id)
                                                }
                                                className="text-xs px-2 py-1 rounded text-gray-300 hover:text-red-400 hover:bg-red-50 transition-colors"
                                            >
                                                Delete
                                            </button>
                                        )}
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </main>
        </div>
    );
};

export default JournalPage;
