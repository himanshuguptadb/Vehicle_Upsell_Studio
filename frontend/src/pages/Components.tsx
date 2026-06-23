import { useEffect, useState } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { api } from "../api";
import { useDraft } from "../store";
import type { Component } from "../types";
import { Button, Card, ErrorBox, Spinner } from "../ui";

const EMPTY: Component = {
  component_key: "", display_name: "", description: "", rubric: "",
  enabled: true, sort_order: 100,
};

export default function ComponentsPage() {
  const [items, setItems] = useState<Component[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState<Component | null>(null);
  const { selectedKeys, setSelectedKeys } = useDraft();

  const load = () => {
    setLoading(true);
    api.listComponents()
      .then((c) => {
        setItems(c);
        // Single-select for the demo: default to the first enabled component.
        if (selectedKeys.length === 0) {
          const first = c.find((x) => x.enabled) || c[0];
          if (first) setSelectedKeys([first.component_key]);
        }
        setError("");
      })
      .catch((e) => setError(String(e.message)))
      .finally(() => setLoading(false));
  };
  useEffect(load, []);

  const save = async () => {
    if (!editing) return;
    try {
      await api.saveComponent(editing);
      setEditing(null);
      load();
    } catch (e: any) { setError(String(e.message)); }
  };

  const remove = async (key: string) => {
    if (!confirm(`Delete component "${key}"?`)) return;
    await api.deleteComponent(key);
    load();
  };

  return (
    <div>
      {editing && (
        <Card title={editing.component_key && items.some((i) => i.component_key === editing.component_key)
          ? "Edit component" : "New component"}>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Key (stable id)">
              <input className="input" value={editing.component_key}
                onChange={(e) => setEditing({ ...editing, component_key: e.target.value })}
                placeholder="e.g. cabin_filter" />
            </Field>
            <Field label="Display name">
              <input className="input" value={editing.display_name}
                onChange={(e) => setEditing({ ...editing, display_name: e.target.value })} />
            </Field>
          </div>
          <Field label="Description">
            <input className="input" value={editing.description}
              onChange={(e) => setEditing({ ...editing, description: e.target.value })} />
          </Field>
          <Field label="Rubric (criteria for Urgent / Upcoming / Good)">
            <textarea className="input h-24" value={editing.rubric}
              onChange={(e) => setEditing({ ...editing, rubric: e.target.value })} />
          </Field>
          <div className="flex gap-2 mt-2">
            <Button onClick={save} disabled={!editing.component_key || !editing.display_name}>Save</Button>
            <Button variant="ghost" onClick={() => setEditing(null)}>Cancel</Button>
          </div>
        </Card>
      )}
      <Card
        title="Vehicle components"
        right={<Button onClick={() => setEditing({ ...EMPTY })}><Plus size={14} className="inline mr-1" />Add</Button>}
      >
        <p className="text-sm text-gray-500 mb-4">
          Pick the component the prompt should analyze for upsell opportunity (one at a time).
          Edit descriptions and rubrics to tune how the LLM classifies it.
        </p>
        {error && <ErrorBox msg={error} />}
        {loading ? <Spinner label="Loading components…" /> : (
          <div className="divide-y divide-gray-100">
            {items.map((c) => (
              <div key={c.component_key} className="py-3 flex items-start gap-3">
                <input
                  type="radio"
                  name="vsu-component"
                  className="mt-1 w-4 h-4 accent-[#FF3621]"
                  checked={selectedKeys.includes(c.component_key)}
                  onChange={() => setSelectedKeys([c.component_key])}
                />
                <div className="flex-1">
                  <div className="font-medium">
                    {c.display_name} <span className="text-gray-400 text-xs">({c.component_key})</span>
                  </div>
                  <div className="text-sm text-gray-600">{c.description}</div>
                  {c.rubric && <div className="text-xs text-gray-400 mt-1">{c.rubric}</div>}
                </div>
                <button className="text-gray-400 hover:text-[#1B3139] p-1" onClick={() => setEditing(c)}>
                  <Pencil size={16} />
                </button>
                <button className="text-gray-400 hover:text-red-600 p-1" onClick={() => remove(c.component_key)}>
                  <Trash2 size={16} />
                </button>
              </div>
            ))}
            {items.length === 0 && (
              <div className="text-sm text-gray-500 py-4">
                No components yet. If this is a fresh deploy, re-run the deploy to seed the catalog.
              </div>
            )}
          </div>
        )}
        <div className="mt-4 text-sm text-gray-500">
          Selected for analysis: <b>{selectedKeys[0] || "none"}</b>
        </div>
      </Card>
      <style>{`.input{width:100%;border:1px solid #e5e7eb;border-radius:.5rem;padding:.5rem .65rem;font-size:.875rem}
        .input:focus{outline:2px solid #FF362133;border-color:#FF3621}`}</style>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block mb-3">
      <span className="text-xs font-medium text-gray-500">{label}</span>
      <div className="mt-1">{children}</div>
    </label>
  );
}
