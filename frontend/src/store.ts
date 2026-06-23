import { create } from "zustand";
import type { Component } from "./types";

interface DraftState {
  model: string;
  selectedKeys: string[];
  promptText: string;
  configId: string | null;
  configName: string;
  // One-shot flag: when set, the Builder keeps the loaded config on its next mount
  // (e.g. arriving via the Configs-tab "Refine" button) instead of defaulting to scratch.
  keepLoaded: boolean;
  setModel: (m: string) => void;
  toggleKey: (k: string) => void;
  setSelectedKeys: (k: string[]) => void;
  setPromptText: (t: string) => void;
  setKeepLoaded: (v: boolean) => void;
  loadConfig: (c: {
    config_id: string; name: string; model_endpoint: string;
    prompt_text: string; components: Component[];
  }) => void;
  reset: () => void;
}

export const useDraft = create<DraftState>((set) => ({
  model: "",
  selectedKeys: [],
  promptText: "",
  configId: null,
  configName: "",
  keepLoaded: false,
  setModel: (model) => set({ model }),
  toggleKey: (k) =>
    set((s) => ({
      selectedKeys: s.selectedKeys.includes(k)
        ? s.selectedKeys.filter((x) => x !== k)
        : [...s.selectedKeys, k],
    })),
  setSelectedKeys: (selectedKeys) => set({ selectedKeys }),
  setPromptText: (promptText) => set({ promptText }),
  setKeepLoaded: (keepLoaded) => set({ keepLoaded }),
  loadConfig: (c) =>
    set({
      configId: c.config_id,
      configName: c.name,
      model: c.model_endpoint,
      promptText: c.prompt_text,
      selectedKeys: (c.components || []).map((x) => x.component_key),
    }),
  reset: () => set({ configId: null, configName: "", promptText: "" }),
}));
