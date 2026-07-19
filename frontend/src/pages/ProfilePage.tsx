import React, { useEffect, useState, useCallback } from "react";
import { useNavigate, Link } from "react-router-dom";
import Header from "../components/Header";
import axios from "axios";
import { User, Therapist } from "../types";
import ProtectedRoute from "../components/ProtectedRoute";

const API = "http://localhost:3000";

interface Memory {
    _id: string;
    content: string;
    memoryType: "instruct" | "info";
    conversationId: string | null;
    createdAt: string;
}

interface SessionState {
    _id: string;
    userId: string;
    conversationId: string;
    riskTrend: string;
    activeThemes: string[];
    activeWarningSignals: string[];
    whatHelpedThisSession: string[];
    lastRiskLevel: string; // "NONE" | "LOW" | "MODERATE" | "HIGH" | "IMMINENT"
    staleness: number;
    createdAt: string;
}

interface RecurringTheme {
    theme: string;
    frequency: number;
    lastSeen: string;
    trend: string;
}

interface CommonTrigger {
    trigger: string;
    frequency: number;
    lastSeen: string;
}

interface KnownApproach {
    approach: string;
    effectiveness: number;
    frequency: number;
    lastUsed: string;
}

interface UserProfile {
    _id: string;
    userId: string;
    recurringThemes: RecurringTheme[];
    commonTriggers: CommonTrigger[];
    preferredSupportStyle: string[];
    knownHelpfulApproaches: KnownApproach[];
    riskBaseline: string;
    riskTrend: string;
    totalSessionsAnalyzed: number;
    stats: {
        totalConversations: number;
        totalMessages: number;
        averageRiskLevel: string;
    };
    createdAt: string;
    updatedAt: string;
}

/* ------------------------------------------------------------------ */
/* User Therapy Profile sub-panel                                       */
/* ------------------------------------------------------------------ */
const UserProfilePanel: React.FC<{ token: string; userId: string }> = ({
    token,
    userId,
}) => {
    const [profile, setProfile] = useState<UserProfile | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    const headers = { Authorization: `Bearer ${token}` };

    useEffect(() => {
        const fetchProfile = async () => {
            setLoading(true);
            try {
                const { data } = await axios.get<UserProfile>(
                    `${API}/api/user-profile/${userId}`,
                    { headers },
                );
                setProfile(data);
            } catch (err) {
                setError("Could not load therapy profile.");
            } finally {
                setLoading(false);
            }
        };
        fetchProfile();
    }, [userId, token]);

    if (loading) return <p className="text-sm text-[#6B7280]">Loading profile…</p>;
    if (error) return <p className="text-sm text-red-500">{error}</p>;
    if (!profile)
        return (
            <p className="text-sm text-[#6B7280]">
                No therapy profile yet.
            </p>
        );

    return (
        <div className="space-y-6">
            {/* Overall Risk */}
            <div>
                <h3 className="text-sm font-semibold text-[#6B7280] mb-3">
                    Risk Assessment
                </h3>
                <div className="grid grid-cols-2 gap-3">
                    <div className="p-3 rounded-lg bg-blue-50 border border-blue-100">
                        <p className="text-xs text-[#6B7280] font-medium">Baseline</p>
                        <p className="text-sm font-bold text-blue-700 mt-1">
                            {profile.riskBaseline}
                        </p>
                    </div>
                    <div
                        className={`p-3 rounded-lg border ${
                            profile.riskTrend === "improving"
                                ? "bg-green-50 border-green-100"
                                : profile.riskTrend === "declining"
                                  ? "bg-red-50 border-red-100"
                                  : "bg-gray-50 border-gray-100"
                        }`}
                    >
                        <p className="text-xs text-[#6B7280] font-medium">Trend</p>
                        <p
                            className={`text-sm font-bold mt-1 ${
                                profile.riskTrend === "improving"
                                    ? "text-green-700"
                                    : profile.riskTrend === "declining"
                                      ? "text-red-700"
                                      : "text-gray-700"
                            }`}
                        >
                            {profile.riskTrend}
                        </p>
                    </div>
                </div>
            </div>

            {/* Stats */}
            <div>
                <h3 className="text-sm font-semibold text-[#6B7280] mb-3">
                    Conversation Statistics
                </h3>
                <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                        <span className="text-[#6B7280]">Total Sessions:</span>
                        <span className="font-medium text-[#1F2937]">
                            {profile.stats.totalConversations}
                        </span>
                    </div>
                    <div className="flex justify-between">
                        <span className="text-[#6B7280]">Total Messages:</span>
                        <span className="font-medium text-[#1F2937]">
                            {profile.stats.totalMessages}
                        </span>
                    </div>
                    <div className="flex justify-between">
                        <span className="text-[#6B7280]">Average Risk Level:</span>
                        <span className="font-medium text-[#1F2937]">
                            {profile.stats.averageRiskLevel}
                        </span>
                    </div>
                </div>
            </div>

            {/* Recurring Themes */}
            {profile.recurringThemes.length > 0 && (
                <div>
                    <h3 className="text-sm font-semibold text-[#6B7280] mb-3">
                        Recurring Themes ({profile.recurringThemes.length})
                    </h3>
                    <div className="space-y-2">
                        {profile.recurringThemes.map((theme) => (
                            <div
                                key={theme.theme}
                                className="p-3 rounded-lg border border-gray-200 bg-gray-50"
                            >
                                <div className="flex items-start justify-between mb-1">
                                    <p className="text-sm font-medium text-[#1F2937]">
                                        {theme.theme}
                                    </p>
                                    <span
                                        className={`px-2 py-0.5 rounded text-xs font-medium ${
                                            theme.trend === "improving"
                                                ? "bg-green-100 text-green-700"
                                                : theme.trend === "worsening"
                                                  ? "bg-red-100 text-red-700"
                                                  : "bg-gray-100 text-gray-700"
                                        }`}
                                    >
                                        {theme.trend}
                                    </span>
                                </div>
                                <p className="text-xs text-[#6B7280]">
                                    Observed {theme.frequency}x (last:{" "}
                                    {new Date(theme.lastSeen).toLocaleDateString()})
                                </p>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Common Triggers */}
            {profile.commonTriggers.length > 0 && (
                <div>
                    <h3 className="text-sm font-semibold text-[#6B7280] mb-3">
                        Common Triggers ({profile.commonTriggers.length})
                    </h3>
                    <div className="space-y-2">
                        {profile.commonTriggers.map((trigger) => (
                            <div
                                key={trigger.trigger}
                                className="p-3 rounded-lg border border-orange-200 bg-orange-50"
                            >
                                <p className="text-sm font-medium text-orange-900">
                                    {trigger.trigger}
                                </p>
                                <p className="text-xs text-orange-700 mt-1">
                                    Frequency: {trigger.frequency}
                                </p>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Most Effective Approaches */}
            {profile.knownHelpfulApproaches.length > 0 && (
                <div>
                    <h3 className="text-sm font-semibold text-[#6B7280] mb-3">
                        Most Effective Approaches
                    </h3>
                    <div className="space-y-2">
                        {profile.knownHelpfulApproaches
                            .sort((a, b) => b.effectiveness - a.effectiveness)
                            .slice(0, 3)
                            .map((approach) => (
                                <div
                                    key={approach.approach}
                                    className="p-3 rounded-lg border border-purple-200 bg-purple-50"
                                >
                                    <div className="flex items-start justify-between">
                                        <p className="text-sm font-medium text-purple-900">
                                            {approach.approach}
                                        </p>
                                        <span className="px-2 py-0.5 rounded text-xs font-bold bg-purple-200 text-purple-800">
                                            {approach.effectiveness}/10
                                        </span>
                                    </div>
                                    <p className="text-xs text-purple-700 mt-1">
                                        Used {approach.frequency}x
                                    </p>
                                </div>
                            ))}
                    </div>
                </div>
            )}

            {/* Preferred Support Style */}
            {profile.preferredSupportStyle.length > 0 && (
                <div>
                    <h3 className="text-sm font-semibold text-[#6B7280] mb-3">
                        Preferred Support Style
                    </h3>
                    <div className="flex flex-wrap gap-2">
                        {profile.preferredSupportStyle.map((style) => (
                            <span
                                key={style}
                                className="px-3 py-1 rounded-full text-xs font-medium bg-indigo-100 text-indigo-700"
                            >
                                {style}
                            </span>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
};

/* ------------------------------------------------------------------ */
/* Memories sub-panel                                                   */
/* ------------------------------------------------------------------ */
const MemoryPanel: React.FC<{ token: string }> = ({ token }) => {
    const [memories, setMemories] = useState<Memory[]>([]);
    const [loadingMem, setLoadingMem] = useState(true);
    const [memError, setMemError] = useState("");

    // add-form state
    const [addContent, setAddContent] = useState("");
    const [addType] = useState<"info" | "instruct">("instruct");
    const [adding, setAdding] = useState(false);

    // edit state
    const [editId, setEditId] = useState<string | null>(null);
    const [editContent, setEditContent] = useState("");
    const [editType] = useState<"info" | "instruct">("instruct");
    const [saving, setSaving] = useState(false);

    const headers = { Authorization: `Bearer ${token}` };

    const fetchMemories = useCallback(async () => {
        setLoadingMem(true);
        try {
            const { data } = await axios.get<Memory[]>(`${API}/api/memories`, {
                headers,
            });
            setMemories(data);
        } catch {
            setMemError("Could not load memories.");
        } finally {
            setLoadingMem(false);
        }
    }, [token]); // eslint-disable-line react-hooks/exhaustive-deps

    useEffect(() => {
        fetchMemories();
    }, [fetchMemories]);

    const handleAdd = async () => {
        if (!addContent.trim()) return;
        setAdding(true);
        try {
            const { data } = await axios.post<Memory>(
                `${API}/api/memories`,
                { content: addContent.trim(), memoryType: addType },
                { headers },
            );
            setMemories((prev) => [data, ...prev]);
            setAddContent("");
        } catch {
            setMemError("Failed to add memory.");
        } finally {
            setAdding(false);
        }
    };

    const startEdit = (m: Memory) => {
        setEditId(m._id);
        setEditContent(m.content);
    };

    const handleSave = async () => {
        if (!editId) return;
        setSaving(true);
        try {
            const { data } = await axios.put<Memory>(
                `${API}/api/memories/${editId}`,
                { content: editContent.trim(), memoryType: editType },
                { headers },
            );
            setMemories((prev) =>
                prev.map((m) => (m._id === editId ? data : m)),
            );
            setEditId(null);
        } catch {
            setMemError("Failed to save changes.");
        } finally {
            setSaving(false);
        }
    };

    const handleDelete = async (id: string) => {
        if (!window.confirm("Delete this memory?")) return;
        try {
            await axios.delete(`${API}/api/memories/${id}`, { headers });
            setMemories((prev) => prev.filter((m) => m._id !== id));
        } catch {
            setMemError("Failed to delete memory.");
        }
    };

    const info = memories.filter((m) => m.memoryType === "info");
    const instruct = memories.filter((m) => m.memoryType === "instruct");

    const MemoryRow: React.FC<{ m: Memory }> = ({ m }) => {
        const isEditing = editId === m._id;
        return (
            <div className="group flex flex-col gap-1 p-3 rounded-lg border border-gray-100 bg-gray-50 hover:bg-white transition-colors">
                {isEditing ? (
                    <>
                        <textarea
                            className="w-full text-sm border border-gray-300 rounded p-2 resize-none focus:outline-none focus:ring-2 focus:ring-[#C66408]"
                            rows={3}
                            value={editContent}
                            onChange={(e) => setEditContent(e.target.value)}
                        />
                        <div className="flex items-center gap-2 mt-1">
                            <button
                                onClick={handleSave}
                                disabled={saving}
                                className="ml-auto px-3 py-1 text-xs rounded bg-[#C66408] text-white hover:bg-[#B35C07] disabled:opacity-50"
                            >
                                {saving ? "Saving…" : "Save"}
                            </button>
                            <button
                                onClick={() => setEditId(null)}
                                className="px-3 py-1 text-xs rounded border border-gray-300 hover:bg-gray-100"
                            >
                                Cancel
                            </button>
                        </div>
                    </>
                ) : (
                    <div className="flex items-start gap-2">
                        <p className="flex-1 text-sm text-[#1F2937] leading-relaxed">
                            {m.content}
                        </p>
                        <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                            {m.memoryType === "instruct" && (
                                <button
                                    onClick={() => startEdit(m)}
                                    title="Edit"
                                    className="p-1 rounded hover:bg-gray-200 text-[#6B7280]"
                                >
                                    ✏️
                                </button>
                            )}
                            <button
                                onClick={() => handleDelete(m._id)}
                                title="Delete"
                                className="p-1 rounded hover:bg-red-100 text-red-400"
                            >
                                🗑️
                            </button>
                        </div>
                    </div>
                )}
                {!isEditing && (
                    <span className="text-[10px] text-[#9CA3AF]">
                        {m.conversationId
                            ? "from conversation"
                            : "added manually"}{" "}
                        · {new Date(m.createdAt).toLocaleDateString()}
                    </span>
                )}
            </div>
        );
    };

    return (
        <div className="mt-8">
            <h2 className="text-sm font-semibold text-[#6B7280] uppercase tracking-wider mb-4">
                Memories stored by companion
            </h2>

            {memError && (
                <p className="text-red-500 text-sm mb-3">{memError}</p>
            )}

            {/* Add form — instruct/preference memories only */}
            <div className="mb-6 p-4 rounded-xl border border-dashed border-[#C66408]/40 bg-[#FFFBF5]">
                <p className="text-xs font-medium text-[#C66408] mb-2">
                    Add a preference or instruction
                </p>
                <textarea
                    rows={2}
                    placeholder="e.g. I prefer shorter responses, or Please avoid giving homework tasks."
                    value={addContent}
                    onChange={(e) => setAddContent(e.target.value)}
                    className="w-full text-sm border border-gray-200 rounded-lg p-2 resize-none focus:outline-none focus:ring-2 focus:ring-[#C66408] mb-2"
                />
                <div className="flex items-center">
                    <button
                        onClick={handleAdd}
                        disabled={adding || !addContent.trim()}
                        className="ml-auto px-4 py-1.5 text-xs rounded-lg bg-[#C66408] text-white hover:bg-[#B35C07] disabled:opacity-50"
                    >
                        {adding ? "Adding…" : "+ Add"}
                    </button>
                </div>
            </div>

            {loadingMem ? (
                <p className="text-sm text-[#6B7280]">Loading memories…</p>
            ) : memories.length === 0 ? (
                <p className="text-sm text-[#6B7280]">
                    No memories yet. The companion will save things it learns
                    about you.
                </p>
            ) : (
                <div className="space-y-6">
                    {info.length > 0 && (
                        <div>
                            <p className="text-xs font-semibold text-[#6B7280] mb-2">
                                Facts &amp; Info ({info.length})
                            </p>
                            <div className="space-y-2">
                                {info.map((m) => (
                                    <MemoryRow key={m._id} m={m} />
                                ))}
                            </div>
                        </div>
                    )}
                    {instruct.length > 0 && (
                        <div>
                            <p className="text-xs font-semibold text-[#6B7280] mb-2">
                                Preferences &amp; Instructions (
                                {instruct.length})
                            </p>
                            <div className="space-y-2">
                                {instruct.map((m) => (
                                    <MemoryRow key={m._id} m={m} />
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

/* ------------------------------------------------------------------ */
/* Session States sub-panel                                             */
/* ------------------------------------------------------------------ */
const SessionStatePanel: React.FC<{ token: string; userId: string }> = ({
    token,
    userId,
}) => {
    const [conversations, setConversations] = useState<
        { _id: string; title: string }[]
    >([]);
    const [loadingConvs, setLoadingConvs] = useState(true);
    const [selectedConvId, setSelectedConvId] = useState<string | null>(null);
    const [sessionStates, setSessionStates] = useState<SessionState[]>([]);
    const [loadingStates, setLoadingStates] = useState(false);
    const [error, setError] = useState("");

    // Fetch user's conversations from API (not mocked)
    useEffect(() => {
        const fetchConversations = async () => {
            setLoadingConvs(true);
            try {
                const { data } = await axios.get(`${API}/api/conversations`, {
                    headers: { Authorization: `Bearer ${token}` },
                });
                // Ensure data is an array
                const convs = Array.isArray(data)
                    ? data
                    : data.conversations || [];
                setConversations(convs);
                if (convs.length > 0) {
                    setSelectedConvId(convs[0]._id);
                }
                if (convs.length === 0) {
                    setError("No conversations found.");
                }
            } catch (err) {
                setError("Could not load conversations.");
                setConversations([]);
            } finally {
                setLoadingConvs(false);
            }
        };
        if (token && userId) {
            fetchConversations();
        }
    }, [token, userId]);

    // Fetch session states for selected conversation (with proper memoization)
    const fetchSessionStates = useCallback(async () => {
        if (!selectedConvId || !token) return;

        setLoadingStates(true);
        try {
            const { data } = await axios.get<SessionState[]>(
                `${API}/api/session-state/user`,
                { headers: { Authorization: `Bearer ${token}` } },
            );
            setSessionStates(data || []);
        } catch (err) {
            setError("Could not load session states.");
            setSessionStates([]);
        } finally {
            setLoadingStates(false);
        }
    }, [selectedConvId, token]);

    // Trigger fetch when deps change
    useEffect(() => {
        fetchSessionStates();
    }, [fetchSessionStates]);

    const selectedStates = sessionStates.filter(
        (s) => s.conversationId === selectedConvId,
    );

    if (loadingConvs) {
        return (
            <div className="mt-8">
                <h2 className="text-sm font-semibold text-[#6B7280] uppercase tracking-wider mb-4">
                    Longitudinal Session States
                </h2>
                <p className="text-sm text-[#6B7280]">Loading conversations…</p>
            </div>
        );
    }

    return (
        <div className="mt-8">
            <h2 className="text-sm font-semibold text-[#6B7280] uppercase tracking-wider mb-4">
                Longitudinal Session States
            </h2>

            {error && <p className="text-red-500 text-sm mb-3">{error}</p>}

            {/* Conversation Dropdown */}
            <div className="mb-6">
                <label className="text-xs font-medium text-[#6B7280] block mb-2">
                    Select Conversation
                </label>
                {conversations.length === 0 ? (
                    <p className="text-sm text-[#6B7280] p-2 bg-gray-50 rounded-lg">
                        No conversations yet.
                    </p>
                ) : (
                    <select
                        value={selectedConvId || ""}
                        onChange={(e) => setSelectedConvId(e.target.value)}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#C66408]"
                    >
                        <option value="">-- Select a conversation --</option>
                        {conversations.map((conv) => (
                            <option key={conv._id} value={conv._id}>
                                {conv.title}
                            </option>
                        ))}
                    </select>
                )}
            </div>

            {/* Admin Level Note */}
            <div className="mb-6 p-4 rounded-lg border-l-4 border-yellow-500 bg-yellow-50">
                <p className="text-xs text-yellow-700 font-medium">
                    ⚠️ <strong>Admin-level assessment needed:</strong> Deeper
                    analysis of session trends requires manual review and
                    clinical judgment. This view is for reference only.
                </p>
            </div>

            {/* Session States Display */}
            {!selectedConvId ? (
                <p className="text-sm text-[#6B7280]">
                    Select a conversation to view session states.
                </p>
            ) : loadingStates ? (
                <p className="text-sm text-[#6B7280]">
                    Loading session states…
                </p>
            ) : selectedStates.length === 0 ? (
                <p className="text-sm text-[#6B7280]">
                    No session states recorded for this conversation.
                </p>
            ) : (
                <div className="space-y-3">
                    {selectedStates.map((state) => (
                        <div
                            key={state._id}
                            className="p-4 rounded-lg border border-gray-200 bg-gray-50"
                        >
                            <div className="flex items-start justify-between mb-2">
                                <p className="text-xs font-semibold text-[#6B7280]">
                                    {new Date(state.createdAt).toLocaleString()}
                                </p>
                                <span
                                    className={`px-2 py-1 rounded text-xs font-medium ${
                                        state.riskTrend === "improving"
                                            ? "bg-green-100 text-green-700"
                                            : state.riskTrend === "declining"
                                              ? "bg-red-100 text-red-700"
                                              : "bg-gray-100 text-gray-700"
                                    }`}
                                >
                                    {state.riskTrend}
                                </span>
                            </div>

                            <div className="space-y-2 text-sm">
                                <div>
                                    <p className="text-xs font-semibold text-[#1F2937]">
                                        Risk Level: {state.lastRiskLevel}
                                    </p>
                                </div>
                                {state.activeThemes.length > 0 && (
                                    <div>
                                        <p className="text-xs font-semibold text-[#6B7280]">
                                            Themes:
                                        </p>
                                        <div className="flex flex-wrap gap-1 mt-1">
                                            {state.activeThemes.map((theme) => (
                                                <span
                                                    key={theme}
                                                    className="px-2 py-0.5 rounded text-xs bg-blue-100 text-blue-700"
                                                >
                                                    {theme}
                                                </span>
                                            ))}
                                        </div>
                                    </div>
                                )}
                                {state.activeWarningSignals.length > 0 && (
                                    <div>
                                        <p className="text-xs font-semibold text-[#6B7280]">
                                            Warning Signals:
                                        </p>
                                        <div className="flex flex-wrap gap-1 mt-1">
                                            {state.activeWarningSignals.map(
                                                (signal) => (
                                                    <span
                                                        key={signal}
                                                        className="px-2 py-0.5 rounded text-xs bg-orange-100 text-orange-700"
                                                    >
                                                        {signal}
                                                    </span>
                                                ),
                                            )}
                                        </div>
                                    </div>
                                )}
                                {state.whatHelpedThisSession.length > 0 && (
                                    <div>
                                        <p className="text-xs font-semibold text-[#6B7280]">
                                            What Helped:
                                        </p>
                                        <p className="text-xs text-[#1F2937] mt-1">
                                            {state.whatHelpedThisSession.join(
                                                ", ",
                                            )}
                                        </p>
                                    </div>
                                )}
                                <p className="text-xs text-[#9CA3AF]">
                                    Staleness:{" "}
                                    {state.staleness === 0
                                        ? "Fresh (LLM)"
                                        : `${state.staleness}+ (Fallback)`}
                                </p>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};

const ProfileContent: React.FC = () => {
    const navigate = useNavigate();
    const [profile, setProfile] = useState<User | Therapist | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [token, setToken] = useState("");

    useEffect(() => {
        const fetchProfile = async () => {
            const raw = localStorage.getItem("user");
            if (!raw) {
                setError("Not logged in");
                setLoading(false);
                return;
            }
            try {
                const userData = JSON.parse(raw);
                if (!userData.token) {
                    setError("Session expired. Please log in.");
                    setLoading(false);
                    return;
                }
                setToken(userData.token);
                const endpoint =
                    userData.userType === "user"
                        ? "http://localhost:3000/api/users/profile"
                        : "http://localhost:3000/api/therapists/profile";
                const { data } = await axios.get(endpoint, {
                    headers: { Authorization: `Bearer ${userData.token}` },
                });
                setProfile(data);
            } catch (err: any) {
                if (err.response?.status === 401) {
                    localStorage.removeItem("user");
                    navigate("/login");
                } else {
                    setError(
                        err.response?.data?.message ||
                            err.message ||
                            "Could not load profile.",
                    );
                }
            } finally {
                setLoading(false);
            }
        };
        fetchProfile();
    }, [navigate]);

    const Spinner = () => (
        <div className="min-h-screen bg-[#F9FAFB] flex items-center justify-center">
            <p className="text-[#6B7280]">Loading profile…</p>
        </div>
    );

    const ErrorPage = ({ msg }: { msg: string }) => (
        <div className="min-h-screen bg-[#F9FAFB]">
            <Header />
            <div className="max-w-md mx-auto mt-20 text-center">
                <p className="text-red-500 mb-4">{msg}</p>
                <Link
                    to="/login"
                    className="text-[#C66408] font-semibold hover:underline"
                >
                    Go to Login
                </Link>
            </div>
        </div>
    );

    if (loading) return <Spinner />;
    if (error) return <ErrorPage msg={error} />;

    const isUser = profile && "username" in profile;
    const displayName = isUser
        ? (profile as User).username
        : (profile as Therapist).name;
    const tags = isUser
        ? (profile as User).interests || []
        : (profile as Therapist).specializations || [];

    return (
        <div className="min-h-screen bg-[#F9FAFB]">
            <Header />
            <main className="max-w-2xl mx-auto px-4 py-12">
                {/* Profile Card */}
                <div className="bg-white rounded-xl shadow-md p-8 border border-gray-100">
                    {/* Avatar + name */}
                    <div className="flex flex-col items-center mb-8">
                        <img
                            src={`https://ui-avatars.com/api/?name=${encodeURIComponent(displayName || "U")}&background=C66408&color=fff&size=96&rounded=true`}
                            alt="avatar"
                            className="w-24 h-24 rounded-full mb-4 shadow-md"
                        />
                        <h1 className="text-2xl font-bold text-[#1F2937]">
                            {displayName}
                        </h1>
                        <p className="text-sm text-[#6B7280] mt-1">
                            {profile?.email}
                        </p>
                        {!isUser && (
                            <span
                                className={`mt-2 px-3 py-1 rounded-full text-xs font-semibold ${
                                    (profile as Therapist).document?.isVerified
                                        ? "bg-green-100 text-green-700"
                                        : "bg-yellow-100 text-yellow-700"
                                }`}
                            >
                                {(profile as Therapist).document?.isVerified
                                    ? "✓ Verified"
                                    : "⏳ Pending Verification"}
                            </span>
                        )}
                    </div>

                    <hr className="border-gray-100 mb-6" />

                    {/* Interests / Specializations */}
                    <div>
                        <h2 className="text-sm font-semibold text-[#6B7280] uppercase tracking-wider mb-3">
                            {isUser ? "Interests" : "Specializations"}
                        </h2>
                        {tags.length > 0 ? (
                            <div className="flex flex-wrap gap-2">
                                {tags.map((t) => (
                                    <span
                                        key={t}
                                        className="px-3 py-1 rounded-full text-sm font-medium bg-[#FFEEDB] text-[#C66408]"
                                    >
                                        {t}
                                    </span>
                                ))}
                            </div>
                        ) : (
                            <p className="text-sm text-[#6B7280]">
                                None added yet.
                            </p>
                        )}
                    </div>

                    {/* Memories — only shown for regular users */}
                    {isUser && token && (
                        <>
                            <hr className="border-gray-100 mt-8 mb-2" />
                            <h2 className="text-sm font-semibold text-[#6B7280] uppercase tracking-wider mb-4">
                                Memories
                            </h2>
                            <MemoryPanel token={token} />
                        </>
                    )}

                    {/* User Therapy Profile — only shown for regular users */}
                    {isUser && token && profile?._id && (
                        <>
                            <hr className="border-gray-100 mt-8 mb-2" />
                            <h2 className="text-sm font-semibold text-[#6B7280] uppercase tracking-wider mb-4">
                                Therapy Profile
                            </h2>
                            <UserProfilePanel token={token} userId={profile._id} />
                        </>
                    )}

                    {/* Session States — only shown for regular users */}
                    {isUser && token && profile?._id && (
                        <>
                            <hr className="border-gray-100 mt-8 mb-2" />
                            <h2 className="text-sm font-semibold text-[#6B7280] uppercase tracking-wider mb-4">
                                Session States
                            </h2>
                            <SessionStatePanel
                                token={token}
                                userId={profile._id}
                            />
                        </>
                    )}
                </div>

                {/* Quick nav back home */}
                <div className="mt-6 text-center">
                    <Link
                        to="/"
                        className="text-sm text-[#6B7280] hover:text-[#C66408] transition-colors"
                    >
                        ← Back to Home
                    </Link>
                </div>
            </main>
        </div>
    );
};

const ProfilePage: React.FC = () => (
    <ProtectedRoute>
        <ProfileContent />
    </ProtectedRoute>
);

export default ProfilePage;
