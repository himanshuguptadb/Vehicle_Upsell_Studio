import { useEffect, useMemo, useState } from "react";
import { Eye, Play, Save, Sparkles, Wand2 } from "lucide-react";
import { api } from "../api";
import { useDraft } from "../store";
import type { Component, Config, RunResponse } from "../types";
import { Button, Card, ClassBadge, ErrorBox, Spinner } from "../ui";
import DistributionBars from "./Distribution";

export default function BuilderPage({ models }: { models: string[]; goCompare: () => void }) {
  const draft = useDraft();
  const [allComponents, setAllComponents] = useState<Component[]>([]);
  const [configs, setConfigs] = useState<Config[]>([]);
  const [instruction, setInstruction] = useState("");
  const [limit, setLimit] = useState(10);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [composed, setComposed] = useState("");
  const [showComposed, setShowComposed] = useState(false);
  const [result, setResult] = useState<RunResponse | null>(null);
  const [saveName, setSaveName] = useState("");

  const loadConfigs = () => api.listConfigs().then(setConfigs).catch(() => {});
  useEffect(() => {
    api.listComponents().then(setAllComponents).catch(() => {});
    loadConfigs();
    // Default the Builder to "from scratch" on entry, unless the user explicitly
    // arrived to refine a saved config (Configs-tab "Refine" sets keepLoaded).
    if (draft.keepLoaded) {
      draft.setKeepLoaded(false);
    } else {
      draft.reset();
      setSaveName("");
    }
  }, []);

  const startFrom = (id: string) => {
    if (id === "scratch") {
      draft.reset();          // clears configId/name/promptText; keeps component + model
      setSaveName("");
      setResult(null);
      return;
    }
    const c = configs.find((x) => x.config_id === id);
    if (c) {
      draft.loadConfig({
        config_id: c.config_id, name: c.name, model_endpoint: c.model_endpoint,
        prompt_text: c.prompt_text, components: c.components,
      });
      setResult(null);
    }
  };

  const selected = useMemo(
    () => allComponents.filter((c) => draft.selectedKeys.includes(c.component_key)),
    [allComponents, draft.selectedKeys]
  );

  const wrap = async (label: string, fn: () => Promise<void>) => {
    setBusy(label); setError("");
    try { await fn(); } catch (e: any) { setError(String(e.message)); } finally { setBusy(""); }
  };

  const generate = () => wrap("generate", async () => {
    const r = await api.generatePrompt({ components: selected, model: draft.model, instruction });
    draft.setPromptText(r.prompt_text);
  });
  const improve = () => wrap("improve", async () => {
    const r = await api.improvePrompt({
      prompt_text: draft.promptText, instruction, components: selected, model: draft.model,
    });
    draft.setPromptText(r.prompt_text);
  });
  const preview = () => wrap("preview", async () => {
    const r = await api.previewPrompt({ prompt_text: draft.promptText, components: selected });
    setComposed(r.composed); setShowComposed(true);
  });
  const runTest = () => wrap("run", async () => {
    const r = await api.run({
      model: draft.model, prompt_text: draft.promptText, components: selected, limit,
    });
    setResult(r);
  });
  // Always create a NEW config — we never overwrite, so every change is tracked as its
  // own version.
  const save = () => wrap("save", async () => {
    const name = (saveName || draft.configName || "Untitled config").trim();
    const payload = {
      name, model_endpoint: draft.model, components: selected, prompt_text: draft.promptText,
    };
    const r = await api.createConfig(payload);
    draft.loadConfig({ ...payload, config_id: r.config_id } as any);
    setSaveName("");
    await loadConfigs();
    alert(`Saved new config “${name}”.`);
  });

  return (
    <div>
      <Card title="1 · Start from">
        <label className="block mb-1">
          <span className="text-xs font-medium text-gray-500">Refine an existing config, or start from scratch</span>
          <select
            className="w-full mt-1 border border-gray-200 rounded-lg px-3 py-2 text-sm"
            value={draft.configId || "scratch"}
            onChange={(e) => startFrom(e.target.value)}
          >
            <option value="scratch">✏️ Start from scratch</option>
            {configs.map((c) => (
              <option key={c.config_id} value={c.config_id}>
                ✎ Refine: {c.name} — {c.model_endpoint}
              </option>
            ))}
          </select>
        </label>
        <p className="text-xs text-gray-400">
          {draft.configId
            ? "Editing a saved config — the prompt below is loaded from it; tweak it and use Improve to refine."
            : "Starting fresh — generate a prompt with AI or write your own below."}
        </p>
      </Card>

      <Card title="2 · Component & model">
        <div className="grid grid-cols-2 gap-4 mb-1">
          <label className="block">
            <span className="text-xs font-medium text-gray-500">Component to analyze</span>
            <select
              className="w-full mt-1 border border-gray-200 rounded-lg px-3 py-2 text-sm"
              value={draft.selectedKeys[0] || ""}
              onChange={(e) => draft.setSelectedKeys(e.target.value ? [e.target.value] : [])}
            >
              {allComponents.length === 0 && <option value="">no components — redeploy to seed</option>}
              {allComponents.map((c) => (
                <option key={c.component_key} value={c.component_key}>{c.display_name}</option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-xs font-medium text-gray-500">LLM (serving endpoint)</span>
            <select
              className="w-full mt-1 border border-gray-200 rounded-lg px-3 py-2 text-sm"
              value={draft.model}
              onChange={(e) => draft.setModel(e.target.value)}
            >
              {models.length === 0 && <option value="">loading…</option>}
              {models.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </label>
        </div>
        <p className="text-xs text-gray-400">
          The model dropdown in the top bar stays in sync with this one.
        </p>
      </Card>

      <Card title="3 · Prompt">
        {selected.length === 0 && (
          <div className="text-sm text-amber-700 bg-amber-50 rounded p-3 mb-3">
            No component selected — pick one above.
          </div>
        )}
        {(() => {
          const hasPrompt = draft.promptText.trim().length > 0;
          return (
            <div className="flex gap-2 mb-1 items-center flex-wrap">
              <input
                className="flex-1 min-w-[240px] border border-gray-200 rounded-lg px-3 py-2 text-sm"
                placeholder={hasPrompt
                  ? "What should change? (e.g. 'be stricter on tread depth')"
                  : "Optional guidance for the new prompt (e.g. 'prioritize safety')"}
                value={instruction}
                onChange={(e) => setInstruction(e.target.value)}
              />
              {!hasPrompt ? (
                <Button onClick={generate} disabled={!!busy || selected.length === 0}>
                  <Sparkles size={14} className="inline mr-1" />
                  {busy === "generate" ? "Generating…" : "Generate with AI"}
                </Button>
              ) : (
                <>
                  <Button onClick={improve} disabled={!!busy || !instruction}>
                    <Wand2 size={14} className="inline mr-1" />
                    {busy === "improve" ? "Improving…" : "Improve"}
                  </Button>
                  <Button variant="ghost" onClick={() => { draft.setPromptText(""); setInstruction(""); }}
                    disabled={!!busy}>
                    Start over
                  </Button>
                </>
              )}
            </div>
          );
        })()}
        <p className="text-xs text-gray-400 mb-3">
          {draft.promptText.trim()
            ? "Refining the prompt below. Use “Start over” to clear it and generate a new one."
            : "Generate a prompt from the selected component, or type your own below."}
        </p>
        <textarea
          className="w-full h-64 border border-gray-200 rounded-lg p-3 font-mono text-xs"
          placeholder="Write the classification prompt here, or generate one with AI…"
          value={draft.promptText}
          onChange={(e) => draft.setPromptText(e.target.value)}
        />
        <div className="flex gap-2 mt-2">
          <Button variant="ghost" onClick={preview} disabled={!!busy}>
            <Eye size={14} className="inline mr-1" />Preview composed prompt
          </Button>
        </div>
        {showComposed && (
          <pre className="mt-3 bg-gray-50 border border-gray-200 rounded-lg p-3 text-xs whitespace-pre-wrap max-h-60 overflow-auto">
            {composed}
          </pre>
        )}
      </Card>

      <Card title="4 · Test on sample data">
        {error && <ErrorBox msg={error} />}
        <div className="flex items-center gap-3 mb-3">
          <label className="text-sm text-gray-600">Rows</label>
          <input type="number" min={1} max={200} value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            className="w-20 border border-gray-200 rounded px-2 py-1 text-sm" />
          <Button onClick={runTest} disabled={!!busy || !draft.promptText || selected.length === 0}>
            <Play size={14} className="inline mr-1" />
            {busy === "run" ? "Running ai_query…" : "Run test"}
          </Button>
          {busy === "run" && <Spinner />}
        </div>

        {result && (
          <>
            {(() => {
              const misses = result.rows.filter(
                (r) => !r.technician_flagged && (r.classification === "Urgent" || r.classification === "Upcoming")
              ).length;
              return (
                <div className="mb-3 text-sm bg-amber-50 text-amber-800 rounded-lg p-3">
                  <b>{misses}</b> opportunit{misses === 1 ? "y" : "ies"} the AI surfaced that the
                  technician did <b>not</b> flag (potential misses).
                </div>
              );
            })()}
            <DistributionBars dist={result.distribution} />
            <div className="overflow-auto max-h-[480px] border border-gray-100 rounded-lg mt-3">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 sticky top-0">
                  <tr className="text-left text-gray-500">
                    <th className="p-2">Svc</th>
                    <th className="p-2 w-2/5">Technician notes</th>
                    <th className="p-2">Component</th>
                    <th className="p-2">AI class</th>
                    <th className="p-2">Technician flagged?</th>
                    <th className="p-2">Reasoning</th>
                  </tr>
                </thead>
                <tbody>
                  {result.rows.map((r, i) => {
                    const aiCatch = !r.technician_flagged
                      && (r.classification === "Urgent" || r.classification === "Upcoming");
                    return (
                      <tr key={i} className={`border-t border-gray-100 align-top ${aiCatch ? "bg-amber-50" : ""}`}>
                        <td className="p-2 text-gray-400">{r.service_id}</td>
                        <td className="p-2 text-gray-500 whitespace-pre-wrap">{r.service_performed}</td>
                        <td className="p-2 font-medium">{r.component_key}</td>
                        <td className="p-2"><ClassBadge value={r.classification} /></td>
                        <td className="p-2">
                          {r.technician_flagged ? (
                            <span className="text-xs font-semibold text-green-700">✓ Yes</span>
                          ) : aiCatch ? (
                            <span className="px-2 py-0.5 rounded text-xs font-semibold bg-amber-100 text-amber-800">⚠ AI catch</span>
                          ) : (
                            <span className="text-xs text-gray-400">No</span>
                          )}
                        </td>
                        <td className="p-2 text-gray-600">{r.reasoning}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Card>

      <Card title="5 · Save config">
        <div className="flex gap-2 items-center flex-wrap">
          <input
            className="flex-1 min-w-[240px] border border-gray-200 rounded-lg px-3 py-2 text-sm"
            placeholder={draft.configName ? `e.g. ${draft.configName} v2` : "Name this version"}
            value={saveName}
            onChange={(e) => setSaveName(e.target.value)}
          />
          <Button onClick={save} disabled={!!busy || !draft.promptText || selected.length === 0}>
            <Save size={14} className="inline mr-1" />
            {busy === "save" ? "Saving…" : "Save as new config"}
          </Button>
        </div>
        <p className="text-xs text-gray-400 mt-2">
          Every save creates a new config — existing ones are never overwritten, so each change
          stays as its own tracked version.
          {draft.configName ? ` Refined from “${draft.configName}”.` : ""}
        </p>
      </Card>
    </div>
  );
}
