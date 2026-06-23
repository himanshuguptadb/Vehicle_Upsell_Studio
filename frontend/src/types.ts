export interface Component {
  component_key: string;
  display_name: string;
  description: string;
  rubric: string;
  enabled: boolean;
  sort_order: number;
}

export interface Config {
  config_id: string;
  name: string;
  description: string;
  model_endpoint: string;
  components: Component[];
  prompt_text: string;
  created_at?: string;
  updated_at?: string;
}

export interface RunResultRow {
  service_id: number;
  service_performed?: string;
  component_key: string;
  classification: string;
  reasoning: string;
  technician_flagged?: boolean;
}

export type Distribution = Record<string, Record<string, number>>;

export interface RunResponse {
  rows: RunResultRow[];
  distribution: Distribution;
  run_id?: string;
}

export interface CompareRow {
  service_id: number;
  component_key: string;
  service_performed?: string;
  a_classification: string | null;
  a_reasoning: string | null;
  b_classification: string | null;
  b_reasoning: string | null;
  differs: boolean;
}

export interface CompareResponse {
  a: { label: string; model: string; prompt?: string; distribution: Distribution };
  b: { label: string; model: string; prompt?: string; distribution: Distribution };
  rows: CompareRow[];
  total: number;
  disagreements: number;
}

export interface Settings {
  catalog: string;
  schema: string;
  warehouse_id: string;
  default_model: string;
  jobs_workspace_dir: string;
  warehouses?: { id: string; name: string; state: string | null }[];
}
