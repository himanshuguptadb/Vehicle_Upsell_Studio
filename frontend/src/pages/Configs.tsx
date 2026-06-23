import { useEffect, useState } from "react";
import { Pencil, Trash2 } from "lucide-react";
import { api } from "../api";
import { useDraft } from "../store";
import type { Config } from "../types";
import { Button, Card, ErrorBox, Spinner } from "../ui";

export default function ConfigsPage({ goBuilder }: { goBuilder: () => void }) {
  const [configs, setConfigs] = useState<Config[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const draft = useDraft();

  const load = () => {
    setLoading(true);
    api.listConfigs().then(setConfigs).catch((e) => setError(String(e.message))).finally(() => setLoading(false));
  };
  useEffect(load, []);

  const edit = (c: Config) => {
    draft.loadConfig({
      config_id: c.config_id, name: c.name, model_endpoint: c.model_endpoint,
      prompt_text: c.prompt_text, components: c.components,
    });
    draft.setKeepLoaded(true); // survive the navigation into the Builder
    goBuilder();
  };
  const remove = async (id: string) => {
    if (!confirm("Delete this config?")) return;
    await api.deleteConfig(id);
    load();
  };

  return (
    <Card title="Saved prompt configs">
      {error && <ErrorBox msg={error} />}
      {loading ? <Spinner label="Loading…" /> : configs.length === 0 ? (
        <div className="text-sm text-gray-500">No saved configs yet. Build one on the Prompt Builder tab.</div>
      ) : (
        <div className="divide-y divide-gray-100">
          {configs.map((c) => (
            <div key={c.config_id} className="py-3 flex items-start gap-3">
              <div className="flex-1">
                <div className="font-medium">{c.name}</div>
                <div className="text-xs text-gray-500">
                  {c.model_endpoint} · {c.components?.length || 0} components
                  {c.updated_at ? ` · updated ${c.updated_at.slice(0, 19)}` : ""}
                </div>
                <div className="text-xs text-gray-400 mt-1 line-clamp-2">{c.prompt_text?.slice(0, 160)}…</div>
              </div>
              <button className="text-gray-400 hover:text-[#1B3139] p-1" onClick={() => edit(c)} title="Edit in builder">
                <Pencil size={16} />
              </button>
              <button className="text-gray-400 hover:text-red-600 p-1" onClick={() => remove(c.config_id)}>
                <Trash2 size={16} />
              </button>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
