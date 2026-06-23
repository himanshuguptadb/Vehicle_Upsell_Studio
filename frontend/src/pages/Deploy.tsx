import { useEffect, useState } from "react";
import { ExternalLink, Rocket } from "lucide-react";
import { api } from "../api";
import type { Config } from "../types";
import { Button, Card, ErrorBox, Spinner } from "../ui";

export default function DeployPage() {
  const [configs, setConfigs] = useState<Config[]>([]);
  const [selected, setSelected] = useState("");
  const [runNow, setRunNow] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<{ job_url: string; run_url?: string } | null>(null);

  useEffect(() => {
    api.listConfigs().then((c) => { setConfigs(c); if (c[0]) setSelected(c[0].config_id); })
      .catch((e) => setError(String(e.message)));
  }, []);

  const deploy = async () => {
    setBusy(true); setError(""); setResult(null);
    try {
      const r = await api.deployJob({ config_id: selected, run_now: runNow });
      setResult(r);
    } catch (e: any) { setError(String(e.message)); } finally { setBusy(false); }
  };

  return (
    <Card title="Deploy a config as a Databricks Job">
      <p className="text-sm text-gray-500 mb-4">
        Creates a Lakeflow Job that runs the selected config's <code>ai_query</code> over the
        <b> full</b> service table, writes a recommendations table, and drafts follow-up emails
        for customers with any <b>Urgent</b> finding.
      </p>
      {error && <ErrorBox msg={error} />}
      <div className="flex items-center gap-3 flex-wrap">
        <select className="border border-gray-200 rounded-lg px-3 py-2 text-sm min-w-[280px]"
          value={selected} onChange={(e) => setSelected(e.target.value)}>
          {configs.length === 0 && <option value="">no saved configs</option>}
          {configs.map((c) => (
            <option key={c.config_id} value={c.config_id}>{c.name} — {c.model_endpoint}</option>
          ))}
        </select>
        <label className="text-sm text-gray-600 flex items-center gap-2">
          <input type="checkbox" className="accent-[#FF3621]" checked={runNow}
            onChange={(e) => setRunNow(e.target.checked)} />
          run immediately
        </label>
        <Button onClick={deploy} disabled={busy || !selected}>
          <Rocket size={14} className="inline mr-1" />
          {busy ? "Creating job…" : "Deploy job"}
        </Button>
        {busy && <Spinner />}
      </div>

      {result && (
        <div className="mt-4 bg-green-50 rounded-lg p-4 text-sm">
          <div className="font-medium text-green-800 mb-2">Job created.</div>
          <div className="flex flex-col gap-1">
            <a className="text-[#FF3621] inline-flex items-center gap-1" href={result.job_url} target="_blank">
              Open job <ExternalLink size={12} />
            </a>
            {result.run_url && (
              <a className="text-[#FF3621] inline-flex items-center gap-1" href={result.run_url} target="_blank">
                View this run <ExternalLink size={12} />
              </a>
            )}
          </div>
        </div>
      )}
    </Card>
  );
}
