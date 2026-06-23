import { useEffect, useMemo, useState } from "react";
import { GitCompare } from "lucide-react";
import { api } from "../api";
import { useDraft } from "../store";
import type { CompareResponse, Component, Config } from "../types";
import { Button, Card, ClassBadge, ErrorBox, Spinner } from "../ui";
import DistributionBars from "./Distribution";

const DRAFT = "__draft__";

export default function ComparePage({ }: { models: string[] }) {
  const [configs, setConfigs] = useState<Config[]>([]);
  const [allComponents, setAllComponents] = useState<Component[]>([]);
  const [a, setA] = useState("");
  const [b, setB] = useState("");
  const [limit, setLimit] = useState(10);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [res, setRes] = useState<CompareResponse | null>(null);
  const [onlyDiffs, setOnlyDiffs] = useState(false);
  const draft = useDraft();

  useEffect(() => {
    api.listConfigs().then((c) => {
      setConfigs(c);
      if (c[0]) setA(c[0].config_id);
      if (c[1]) setB(c[1].config_id);
    }).catch((e) => setError(String(e.message)));
    api.listComponents().then(setAllComponents).catch(() => {});
  }, []);

  const draftRef = () => ({
    label: draft.configName || "(current draft)",
    model: draft.model,
    prompt_text: draft.promptText,
    components: allComponents.filter((c) => draft.selectedKeys.includes(c.component_key)),
  });
  const refFor = (val: string) => (val === DRAFT ? draftRef() : { config_id: val });

  const run = async () => {
    setBusy(true); setError(""); setRes(null);
    try {
      setRes(await api.compare({ a: refFor(a), b: refFor(b), limit }));
    } catch (e: any) { setError(String(e.message)); } finally { setBusy(false); }
  };

  const rows = useMemo(
    () => (res ? (onlyDiffs ? res.rows.filter((r) => r.differs) : res.rows) : []),
    [res, onlyDiffs]
  );

  return (
    <div>
      <Card title="Compare two configs on the same sample">
        {error && <ErrorBox msg={error} />}
        <div className="grid grid-cols-2 gap-4">
          <Selector label="Config A" value={a} onChange={setA} configs={configs} />
          <Selector label="Config B" value={b} onChange={setB} configs={configs} />
        </div>
        <div className="flex items-center gap-3 mt-4">
          <label className="text-sm text-gray-600">Rows</label>
          <input type="number" min={1} max={200} value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            className="w-20 border border-gray-200 rounded px-2 py-1 text-sm" />
          <Button onClick={run} disabled={busy || !a || !b}>
            <GitCompare size={14} className="inline mr-1" />
            {busy ? "Running both…" : "Compare"}
          </Button>
          {busy && <Spinner />}
        </div>
      </Card>

      {res && (
        <>
          <Card title={`Result — ${res.disagreements} of ${res.total} disagree`}>
            <div className="grid grid-cols-2 gap-6">
              <div>
                <div className="text-sm font-semibold mb-2">A · {res.a.label}
                  <span className="text-xs text-gray-400 font-normal"> ({res.a.model})</span></div>
                <DistributionBars dist={res.a.distribution} />
              </div>
              <div>
                <div className="text-sm font-semibold mb-2">B · {res.b.label}
                  <span className="text-xs text-gray-400 font-normal"> ({res.b.model})</span></div>
                <DistributionBars dist={res.b.distribution} />
              </div>
            </div>
          </Card>

          <Card title="Prompts">
            <div className="grid grid-cols-2 gap-6">
              <div>
                <div className="text-sm font-semibold mb-2">A · {res.a.label}
                  <span className="text-xs text-gray-400 font-normal"> ({res.a.model})</span></div>
                <pre className="bg-gray-50 border border-gray-200 rounded-lg p-3 text-xs whitespace-pre-wrap max-h-72 overflow-auto">
                  {res.a.prompt || "(no prompt)"}
                </pre>
              </div>
              <div>
                <div className="text-sm font-semibold mb-2">B · {res.b.label}
                  <span className="text-xs text-gray-400 font-normal"> ({res.b.model})</span></div>
                <pre className="bg-gray-50 border border-gray-200 rounded-lg p-3 text-xs whitespace-pre-wrap max-h-72 overflow-auto">
                  {res.b.prompt || "(no prompt)"}
                </pre>
              </div>
            </div>
          </Card>

          <Card title="Row-level comparison"
            right={
              <label className="text-sm text-gray-500 flex items-center gap-2">
                <input type="checkbox" className="accent-[#FF3621]" checked={onlyDiffs}
                  onChange={(e) => setOnlyDiffs(e.target.checked)} />
                disagreements only
              </label>
            }>
            <div className="overflow-auto max-h-[520px] border border-gray-100 rounded-lg">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 sticky top-0">
                  <tr className="text-left text-gray-500">
                    <th className="p-2">Svc</th>
                    <th className="p-2 w-1/3">Technician notes</th>
                    <th className="p-2">Component</th>
                    <th className="p-2">A</th>
                    <th className="p-2">B</th>
                    <th className="p-2">B reasoning</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => (
                    <tr key={i} className={`border-t border-gray-100 align-top ${r.differs ? "bg-amber-50" : ""}`}>
                      <td className="p-2 text-gray-400">{r.service_id}</td>
                      <td className="p-2 text-gray-500 whitespace-pre-wrap">{r.service_performed}</td>
                      <td className="p-2 font-medium">{r.component_key}</td>
                      <td className="p-2"><ClassBadge value={r.a_classification} /></td>
                      <td className="p-2"><ClassBadge value={r.b_classification} /></td>
                      <td className="p-2 text-gray-600">{r.b_reasoning}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}

function Selector({ label, value, onChange, configs }: {
  label: string; value: string; onChange: (v: string) => void; configs: Config[];
}) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-gray-500">{label}</span>
      <select className="w-full mt-1 border border-gray-200 rounded-lg px-3 py-2 text-sm"
        value={value} onChange={(e) => onChange(e.target.value)}>
        <option value={DRAFT}>(current draft from builder)</option>
        {configs.map((c) => (
          <option key={c.config_id} value={c.config_id}>{c.name} — {c.model_endpoint}</option>
        ))}
      </select>
    </label>
  );
}
