import type {
  CompareResponse, Component, Config, RunResponse, Settings,
} from "./types";

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  const data = text ? JSON.parse(text) : {};
  if (!res.ok) {
    throw new Error(data?.error || data?.detail || `${res.status} ${res.statusText}`);
  }
  return data as T;
}

export const api = {
  models: () => req<{ models: { name: string }[]; default: string }>("GET", "/api/models"),

  listComponents: () => req<Component[]>("GET", "/api/components"),
  saveComponent: (c: Partial<Component>) => req("POST", "/api/components", c),
  deleteComponent: (key: string) =>
    req("DELETE", `/api/components/${encodeURIComponent(key)}`),

  listConfigs: () => req<Config[]>("GET", "/api/configs"),
  getConfig: (id: string) => req<Config>("GET", `/api/configs/${id}`),
  createConfig: (c: Partial<Config>) =>
    req<{ config_id: string }>("POST", "/api/configs", c),
  deleteConfig: (id: string) => req("DELETE", `/api/configs/${id}`),

  generatePrompt: (b: { components: Component[]; model: string; instruction?: string }) =>
    req<{ prompt_text: string }>("POST", "/api/prompt/generate", b),
  improvePrompt: (b: {
    prompt_text: string; instruction: string; components: Component[]; model: string;
  }) => req<{ prompt_text: string }>("POST", "/api/prompt/improve", b),
  previewPrompt: (b: { prompt_text: string; components: Component[] }) =>
    req<{ composed: string }>("POST", "/api/prompt/preview", b),

  run: (b: {
    model: string; prompt_text: string; components: Component[];
    source_table?: string; limit?: number; persist?: boolean;
    config_id?: string; config_name?: string;
  }) => req<RunResponse>("POST", "/api/run", b),

  compare: (b: {
    a: { config_id?: string; label?: string; model?: string; prompt_text?: string; components?: Component[] };
    b: { config_id?: string; label?: string; model?: string; prompt_text?: string; components?: Component[] };
    limit?: number; source_table?: string;
  }) => req<CompareResponse>("POST", "/api/compare", b),

  sampleStatus: () =>
    req<{ tables: Record<string, number | null>; ready: boolean }>("GET", "/api/sample/status"),
  generateSample: (b: { rows: number; model?: string }) =>
    req<{ run_id: number; url: string }>("POST", "/api/sample/generate", b),
  sampleRunStatus: (run_id: number) =>
    req<{ life_cycle_state: string; result_state: string | null }>(
      "GET", `/api/sample/run-status?run_id=${run_id}`),

  deployJob: (b: { config_id: string; run_now: boolean }) =>
    req<{ job_id: number; job_url: string; run_id?: number; run_url?: string }>(
      "POST", "/api/deploy-job", b),

  getSettings: () => req<Settings>("GET", "/api/settings"),
  updateSettings: (b: Partial<Settings> & { schema_name?: string }) =>
    req<Settings>("PATCH", "/api/settings", b),
  bootstrap: () => req("POST", "/api/bootstrap"),
};
