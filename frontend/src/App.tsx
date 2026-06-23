import { useEffect, useState } from "react";
import { Boxes, FlaskConical, GitCompare, HelpCircle, Rocket, Save } from "lucide-react";
import { api } from "./api";
import { useDraft } from "./store";
import ComponentsPage from "./pages/Components";
import BuilderPage from "./pages/Builder";
import ConfigsPage from "./pages/Configs";
import ComparePage from "./pages/Compare";
import DeployPage from "./pages/Deploy";
import HelpPage from "./pages/Help";

type Tab = "components" | "builder" | "configs" | "compare" | "deploy" | "help";

// NOTE: the Settings tab was intentionally removed so no one can accidentally change the
// target catalog/schema/warehouse/model or regenerate (overwrite) the curated demo data
// from the UI. Those are fixed at deploy time via app.yaml; re-seeding is an operator task.
const TABS: { id: Tab; label: string; icon: typeof Boxes }[] = [
  { id: "components", label: "Components", icon: Boxes },
  { id: "builder", label: "Prompt Builder", icon: FlaskConical },
  { id: "configs", label: "Saved Configs", icon: Save },
  { id: "compare", label: "Compare", icon: GitCompare },
  { id: "deploy", label: "Deploy", icon: Rocket },
  { id: "help", label: "Help", icon: HelpCircle },
];

export default function App() {
  const [tab, setTab] = useState<Tab>("components");
  const { model, setModel } = useDraft();
  const [models, setModels] = useState<string[]>([]);

  useEffect(() => {
    api.models().then((r) => {
      setModels(r.models.map((m) => m.name));
      if (!model) setModel(r.default || r.models[0]?.name || "");
    }).catch(() => {});
  }, []);

  return (
    <div className="min-h-full flex flex-col">
      <header className="bg-[#1B3139] text-white px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 rounded bg-[#FF3621] flex items-center justify-center font-bold text-sm">V</div>
          <div>
            <div className="font-semibold leading-tight">Vehicle Service Upsell Studio</div>
            <div className="text-xs text-gray-300">Build · test · compare · deploy ai_query upsell configs</div>
          </div>
        </div>
      </header>

      <nav className="bg-white border-b border-gray-200 px-4 flex gap-1">
        {TABS.map((t) => {
          const Icon = t.icon;
          const active = tab === t.id;
          return (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition ${
                active ? "border-[#FF3621] text-[#FF3621]" : "border-transparent text-gray-500 hover:text-[#1B3139]"
              }`}
            >
              <Icon size={16} /> {t.label}
            </button>
          );
        })}
      </nav>

      <main className="flex-1 max-w-6xl w-full mx-auto p-6">
        {tab === "components" && <ComponentsPage />}
        {tab === "builder" && <BuilderPage models={models} goCompare={() => setTab("compare")} />}
        {tab === "configs" && <ConfigsPage goBuilder={() => setTab("builder")} />}
        {tab === "compare" && <ComparePage models={models} />}
        {tab === "deploy" && <DeployPage />}
        {tab === "help" && <HelpPage />}
      </main>
    </div>
  );
}
