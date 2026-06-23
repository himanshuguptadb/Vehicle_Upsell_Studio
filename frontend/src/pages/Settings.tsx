import { useEffect, useState } from "react";
import { Database, Hammer, RefreshCw } from "lucide-react";
import { api } from "../api";
import type { Settings } from "../types";
import { Button, Card, ErrorBox, Spinner } from "../ui";

export default function SettingsPage() {
  const [s, setS] = useState<Settings | null>(null);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState("");
  const [rows, setRows] = useState(300);
  const [sample, setSample] = useState<{ tables: Record<string, number | null>; ready: boolean } | null>(null);
  const [genRun, setGenRun] = useState<{ run_id: number; status?: string } | null>(null);

  const load = () => api.getSettings().then(setS).catch((e) => setError(String(e.message)));
  const loadSample = () => api.sampleStatus().then(setSample).catch(() => {});
  useEffect(() => { load(); loadSample(); }, []);

  const wrap = (label: string, fn: () => Promise<void>) => async () => {
    setBusy(label); setError(""); setMsg("");
    try { await fn(); } catch (e: any) { setError(String(e.message)); } finally { setBusy(""); }
  };

  const saveSettings = wrap("save", async () => {
    if (!s) return;
    await api.updateSettings({
      catalog: s.catalog, schema_name: s.schema, warehouse_id: s.warehouse_id,
      default_model: s.default_model,
    });
    setMsg("Settings updated.");
  });

  const bootstrap = wrap("bootstrap", async () => {
    await api.bootstrap();
    setMsg("Schema + tables created and components seeded.");
  });

  const generate = wrap("gen", async () => {
    const r = await api.generateSample({ rows, model: s?.default_model });
    setGenRun({ run_id: r.run_id });
    poll(r.run_id);
  });

  const poll = async (run_id: number) => {
    const st = await api.sampleRunStatus(run_id);
    setGenRun({ run_id, status: `${st.life_cycle_state}${st.result_state ? " / " + st.result_state : ""}` });
    if (st.life_cycle_state && !["TERMINATED", "INTERNAL_ERROR", "SKIPPED"].includes(st.life_cycle_state)) {
      setTimeout(() => poll(run_id), 5000);
    } else {
      loadSample();
    }
  };

  if (!s) return <Spinner label="Loading settings…" />;

  return (
    <div>
      {error && <ErrorBox msg={error} />}
      {msg && <div className="bg-green-50 text-green-700 text-sm rounded-lg p-3 mb-3">{msg}</div>}

      <Card title="Target location">
        <div className="grid grid-cols-2 gap-3">
          <Field label="Catalog"><input className="inp" value={s.catalog}
            onChange={(e) => setS({ ...s, catalog: e.target.value })} /></Field>
          <Field label="Schema"><input className="inp" value={s.schema}
            onChange={(e) => setS({ ...s, schema: e.target.value })} /></Field>
          <Field label="SQL Warehouse">
            <select className="inp" value={s.warehouse_id}
              onChange={(e) => setS({ ...s, warehouse_id: e.target.value })}>
              {!s.warehouses?.some((w) => w.id === s.warehouse_id) && (
                <option value={s.warehouse_id}>{s.warehouse_id || "(none)"}</option>
              )}
              {s.warehouses?.map((w) => (
                <option key={w.id} value={w.id}>{w.name} ({w.state})</option>
              ))}
            </select>
          </Field>
          <Field label="Default model"><input className="inp" value={s.default_model}
            onChange={(e) => setS({ ...s, default_model: e.target.value })} /></Field>
        </div>
        <div className="flex gap-2 mt-3">
          <Button onClick={saveSettings} disabled={!!busy}>Save settings</Button>
          <Button variant="ghost" onClick={bootstrap} disabled={!!busy}>
            <Hammer size={14} className="inline mr-1" />
            {busy === "bootstrap" ? "Bootstrapping…" : "Bootstrap schema + seed components"}
          </Button>
        </div>
      </Card>

      <Card title="Sample data"
        right={<button className="text-gray-400 hover:text-[#1B3139]" onClick={loadSample}><RefreshCw size={16} /></button>}>
        <div className="flex gap-4 text-sm mb-3">
          {sample ? Object.entries(sample.tables).map(([t, n]) => (
            <div key={t} className="flex items-center gap-1">
              <Database size={14} className={n ? "text-green-600" : "text-gray-300"} />
              <span className="text-gray-600">{t}:</span>
              <span className="font-medium">{n ?? "—"}</span>
            </div>
          )) : <Spinner />}
        </div>
        <div className="flex items-center gap-3">
          <label className="text-sm text-gray-600">Customers</label>
          <input type="number" min={10} max={2000} value={rows}
            onChange={(e) => setRows(Number(e.target.value))}
            className="w-24 border border-gray-200 rounded px-2 py-1 text-sm" />
          <Button onClick={generate} disabled={!!busy}>
            {busy === "gen" ? "Submitting job…" : "Generate / regenerate sample data"}
          </Button>
          {genRun && <span className="text-sm text-gray-500">run {genRun.run_id}: {genRun.status || "submitted"}</span>}
        </div>
        <p className="text-xs text-gray-400 mt-2">
          Runs a notebook job that creates synthetic customers, vehicles, technicians and
          services (with LLM-generated technician notes). Takes a couple of minutes.
        </p>
      </Card>

      <style>{`.inp{width:100%;border:1px solid #e5e7eb;border-radius:.5rem;padding:.5rem .65rem;font-size:.875rem}`}</style>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block mb-2">
      <span className="text-xs font-medium text-gray-500">{label}</span>
      <div className="mt-1">{children}</div>
    </label>
  );
}
