"use client";

// Next.js 14 (App Router) patient Q&A page with a Patient/Doctor toggle.
import React, { useCallback, useMemo, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8080";

type Citation = { title: string; document_id: string; page?: number; section?: string; };
type Answer = { answer: string; citations: Citation[]; guardrails: Record<string, any>; latency_ms: number; };

export default function PatientQA() {
  const [question, setQuestion] = useState("");
  const [mode, setMode] = useState<"PATIENT" | "PROVIDER">("PATIENT");
  const [data, setData] = useState<Answer | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canAsk = useMemo(() => question.trim().length > 3 && !loading, [question, loading]);

  const ask = useCallback(async () => {
    if (!canAsk) return;
    setLoading(true); setError(null); setData(null);
    try {
      const res = await fetch(`${API_BASE}/rag/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: question.trim(), actor: mode, org_id: "demo" }),
      });
      if (!res.ok) throw new Error(await res.text() || `HTTP ${res.status}`);
      const json: Answer = await res.json();
      setData(json);
    } catch (e: any) { setError(e?.message || "Something went wrong"); }
    finally { setLoading(false); }
  }, [question, mode, canAsk]);

  const exampleQs = [
    "What about VTE prophylaxis after TKA?",
    "Do I need nasal decolonization before hip replacement?",
    "When can I start walking after arthroscopy?",
  ];

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-3xl mx-auto p-6 space-y-6">
        <header className="flex items-center justify-between">
          <h1 className="text-2xl font-semibold">Orthopedics Assistant</h1>
          <ModeToggle mode={mode} onChange={setMode} />
        </header>

        <Disclaimer mode={mode} />

        <div className="bg-white rounded-2xl shadow p-4 space-y-3">
          <label className="block text-sm font-medium text-gray-700">Your question</label>
          <textarea
            className="w-full rounded-xl border p-3 focus:outline-none focus:ring-2"
            rows={3}
            placeholder="Type your question…"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) ask(); }}
          />
          <div className="flex flex-wrap gap-2">
            {exampleQs.map((q) => (
              <button key={q} type="button" onClick={() => setQuestion(q)}
                      className="text-sm px-3 py-1 rounded-full border hover:bg-gray-100">
                {q}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-3">
            <button disabled={!canAsk} onClick={ask}
                    className={`px-4 py-2 rounded-xl text-white ${canAsk ? "bg-blue-600 hover:bg-blue-700" : "bg-gray-400"}`}>
              {loading ? "Thinking…" : "Ask"}
            </button>
            <span className="text-xs text-gray-500">Press ⌘/Ctrl + Enter to send</span>
          </div>
        </div>

        {error && <div className="bg-red-50 border border-red-200 text-red-800 p-3 rounded-xl">{error}</div>}
        {data && <AnswerCard mode={mode} data={data} />}

        <footer className="text-xs text-gray-500 pt-6">v0.1 • API: {API_BASE}</footer>
      </div>
    </div>
  );
}

function ModeToggle({
  mode, onChange,
}: { mode: "PATIENT" | "PROVIDER"; onChange: (m: "PATIENT" | "PROVIDER") => void; }) {
  return (
    <div className="inline-flex items-center rounded-xl border overflow-hidden">
      {(["PATIENT", "PROVIDER"] as const).map((m) => (
        <button key={m} onClick={() => onChange(m)}
                className={`px-3 py-1 text-sm ${mode === m ? "bg-blue-600 text-white" : "bg-white"}`}>
          {m === "PATIENT" ? "Patient view" : "Doctor view"}
        </button>
      ))}
    </div>
  );
}

function Disclaimer({ mode }: { mode: "PATIENT" | "PROVIDER" }) {
  if (mode === "PATIENT") {
    return (
      <div className="bg-amber-50 border border-amber-200 text-amber-900 p-3 rounded-xl text-sm">
        This tool does not give medical advice or handle emergencies. It summarizes your clinic’s
        approved orthopedic materials. If you have urgent symptoms, call your clinic or emergency services.
      </div>
    );
  }
  return (
    <div className="bg-slate-50 border border-slate-200 text-slate-700 p-3 rounded-xl text-sm">
      Doctor view shows the same answer with explicit citations and timing. Use the admin app to manage sources/precedence.
    </div>
  );
}

function AnswerCard({ mode, data }: { mode: "PATIENT" | "PROVIDER"; data: Answer }) {
  const { answer, citations, latency_ms } = data;
  return (
    <div className="bg-white rounded-2xl shadow p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Answer</h2>
        <span className="text-xs text-gray-500">Latency: {latency_ms} ms</span>
      </div>

      <div className="prose max-w-none">
        <p className="whitespace-pre-wrap">{answer}</p>
      </div>

      <div>
        <h3 className="text-sm font-medium text-gray-700 mb-2">Citations</h3>
        {citations.length === 0 ? (
          <p className="text-sm text-gray-500">None</p>
        ) : (
          <ul className="list-decimal pl-5 space-y-1 text-sm">
            {citations.map((c, idx) => (
              <li key={idx}>
                <span className="font-medium">{c.title}</span>
                {c.section ? ` — ${c.section}` : ""}
                {typeof c.page === "number" ? ` (p.${c.page})` : ""}
              </li>
            ))}
          </ul>
        )}
      </div>

      {mode === "PATIENT" ? (
        <div className="text-xs text-gray-500">
          If anything here conflicts with what your surgeon told you, follow your surgeon’s guidance.
        </div>
      ) : (
        <div className="text-xs text-gray-500">
          Provider note: response style depends on the <code>actor</code> sent to the API. Tune prompts in the backend for more technical output.
        </div>
      )}
    </div>
  );
}
