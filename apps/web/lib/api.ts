export type Decision = 'ALLOW' | 'VERIFY' | 'BLOCK';

export type RiskQueueItem = {
  transaction_id: string;
  agent_id: string;
  agent_name: string;
  merchant_id: string;
  merchant_name: string;
  amount: string;
  currency: string;
  status: string;
  risk_score: string;
  risk_band: string;
  decision: Decision;
  model_version: string;
  policy_version: number;
  reason_codes: string[];
  occurred_at: string;
};

export type RiskQueueResponse = {
  items: RiskQueueItem[];
  total: number;
  limit: number;
  offset: number;
};

export type TransactionFeatureSet = {
  version: string;
  values: Record<string, number>;
  computed_at: string;
};

export type TransactionDetail = {
  transaction: RiskQueueItem;
  features: TransactionFeatureSet | null;
  prediction: { model_version: string; score: string; risk_band: string; signals: { signals?: string[] }; created_at: string } | null;
  policy_evaluation: { policy_version: number; result: string; violations: string[]; evaluated_at: string } | null;
  decision_record: { decision: Decision; risk_score: string; risk_band: string; model_version: string; policy_version: number; reason_codes: string[] } | null;
  reviews: { id: string; transaction_id: string; reviewer_id: string; outcome: string; note: string | null; created_at: string }[];
  audit_events: { id: string; transaction_id: string | null; event_type: string; actor_type: string; actor_id: string | null; payload: Record<string, unknown>; occurred_at: string }[];
  investigation: { status: string; prompt_version: string | null; evidence_hash: string | null; result: Record<string, unknown> } | null;
  payment_order: { provider: string; provider_order_id: string; state: string; amount_minor: number; currency: string } | null;
  provider_payment: { provider_payment_id: string; state: string; raw_event: Record<string, unknown> } | null;
};

export type RiskMetrics = {
  evaluations: number;
  high_risk: number;
  verification: number;
  blocked: number;
  allowed: number;
};

export type PolicyItem = {
  id: string;
  agent_id: string;
  version: number;
  is_active: boolean;
  rules: Record<string, unknown>;
  created_at: string;
};

export type ModelItem = {
  version: string;
  status: string;
  artifact_sha256: string;
  metrics: Record<string, unknown>;
  training_config: Record<string, unknown>;
  created_at: string;
};

export type AuditItem = {
  id: string;
  transaction_id: string | null;
  event_type: string;
  actor_type: string;
  actor_id: string | null;
  payload: Record<string, unknown>;
  occurred_at: string;
};

export type HealthResponse = { status: string; reason?: string };

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    cache: 'no-store',
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.error?.message ?? `API request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export const getRiskMetrics = () => api<RiskMetrics>('/risk/metrics');
export const getRiskQueue = (params: { limit?: number; offset?: number; decision?: string; risk_band?: string } = {}) => {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) if (value !== undefined) search.set(key, String(value));
  return api<RiskQueueResponse>(`/risk/transactions?${search.toString()}`);
};
export const getTransaction = (id: string) => api<TransactionDetail>(`/risk/transactions/${id}`);
export const getPolicies = () => api<PolicyItem[]>('/policies');
export const getModels = () => api<ModelItem[]>('/models');
export const getAudit = (limit = 100) => api<AuditItem[]>(`/audit?limit=${limit}`);
export const getHealth = () => api<HealthResponse>('/health/ready', { cache: 'no-store' });

export const createReview = (id: string, body: { reviewer_id: string; outcome: 'APPROVE' | 'REJECT' | 'ESCALATE'; note?: string }) =>
  api<TransactionDetail['reviews'][number]>(`/risk/transactions/${id}/review`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
