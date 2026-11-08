// Typed client for the Udyam Digital API (FastAPI on Render).
export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export type Need = string;

export interface BusinessProfile {
  business_name?: string | null;
  business_type?: string | null;
  segment?: "micro" | "prof" | "multi" | "mfg" | null;
  employees?: number | null;
  sites?: number | null;
  city?: string | null;
  city_tier?: 1 | 2 | null;
  has_gstin?: boolean | null;
  gstin?: string | null;
  current_monthly_spend?: number | null;
  needs: Need[];
  budget_monthly?: number | null;
  language: string;
  [k: string]: unknown;
}

export interface LineItem {
  product_id: string;
  name: string;
  category: string;
  unit: string;
  quantity: number;
  unit_price: number;
  monthly: number;
  setup_fee: number;
  min_contract_months: number;
  install_days: number;
  selected: boolean;
  core: boolean;
  reason: string;
  auto_added_for?: string | null;
}

export interface ExcludedItem { product_id: string; name: string; reason: string; unlock: string }

export interface Quote {
  items: LineItem[];
  excluded: ExcludedItem[];
  monthly_total: number;
  gst_amount: number;
  monthly_total_with_gst: number;
  one_time_setup: number;
  contract_months: number;
  expected_activation_days: number;
  current_monthly_spend?: number | null;
  budget_monthly?: number | null;
  over_budget_by: number;
  notes: string[];
}

export interface Recommendation {
  profile: BusinessProfile;
  segment: string;
  segment_label: string;
  quote: Quote;
  headline: string;
}

export interface ChatResponse {
  session_id: string;
  mode: "ai" | "guided";
  reply: string;
  quick_replies: string[];
  profile: BusinessProfile;
  missing: string[];
  recommendation?: Recommendation | null;
}

export interface KycCheck { id: string; doc: string; title: string; status: "pass" | "warn" | "fail"; detail: string; fix: string }
export interface KycReport {
  verdict: "verified" | "needs_action";
  business_name?: string | null;
  gstin_masked?: string | null;
  gst_status?: string | null;
  checks: KycCheck[];
  blocks_gst_products: boolean;
  summary: { pass: number; warn: number; fail: number };
}

export interface OrderView {
  id: string;
  business_name: string;
  created_at: string;
  monthly_total: number;
  one_time_setup: number;
  contract_months: number;
  expected_activation: string;
  kyc_verdict: string;
  channel: string;
  contact_phone_masked?: string | null;
  stage_index: number;
  timeline: { key: string; title: string; description: string; done: boolean; current: boolean; at?: string | null }[];
  lines: { product_id: string; name: string; quantity: number; expected_by: string; status: string }[];
  notifications: { at: string; via: string; message: string }[];
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: init?.body instanceof FormData ? init?.headers : { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!res.ok) {
    let msg = `Request failed (${res.status})`;
    try {
      const j = await res.json();
      msg = typeof j.detail === "string" ? j.detail : msg;
    } catch {}
    throw new Error(msg);
  }
  return res.json() as Promise<T>;
}

const post = <T,>(path: string, body?: unknown) => call<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export const api = {
  meta: () => call<{ ai_enabled: boolean; languages: Record<string, string> }>("/api/meta"),
  advisorStart: (language: string) => post<ChatResponse>("/api/advisor/start", { language }),
  advisorChat: (session_id: string, message: string, show_plan = false) => post<ChatResponse>("/api/advisor/chat", { session_id, message, show_plan }),
  requote: (profile: BusinessProfile, items: LineItem[], toggles: Record<string, boolean>, quantities: Record<string, number>) =>
    post<Quote>("/api/quote/requote", { profile, items, toggles, quantities }),
  gstin: (g: string) => call<Record<string, any>>(`/api/registry/gstin/${encodeURIComponent(g)}`),
  notice: (lang: string) => call<{ title: string; points: string[]; purposes: Record<string, string>; required_documents: { type: string; label: string }[] }>(`/api/kyc/notice?lang=${lang}`),
  consent: (language: string, purposes: string[]) => post<{ session_id: string; consent_id: number; expires_in_minutes: number }>("/api/kyc/consent", { language, purposes }),
  upload: (sid: string, doc_type: string, file: File) => {
    const fd = new FormData();
    fd.append("doc_type", doc_type);
    fd.append("file", file);
    return call<any>(`/api/kyc/${sid}/upload`, { method: "POST", body: fd });
  },
  sample: (sid: string, applicant: string) => post<any>(`/api/kyc/${sid}/sample/${applicant}`),
  declareGstin: (sid: string, gstin: string) => post<any>(`/api/kyc/${sid}/declare-gstin`, { gstin }),
  report: (sid: string) => call<KycReport>(`/api/kyc/${sid}/report`),
  withdraw: (sid: string) => call<any>(`/api/kyc/${sid}`, { method: "DELETE" }),
  createOrder: (body: { profile: BusinessProfile; items: LineItem[]; kyc_session_id?: string; contact_phone?: string; preferred_slot?: string; channel?: string; partner_code?: string }) =>
    post<OrderView>("/api/orders", body),
  order: (id: string) => call<OrderView>(`/api/orders/${encodeURIComponent(id)}`),
  advance: (id: string) => post<OrderView>(`/api/orders/${encodeURIComponent(id)}/advance`),
  callList: (limit = 30) => call<{ model: any; leads: any[] }>(`/api/partner/call-list?limit=${limit}`),
  advisorLeads: () => call<any[]>("/api/partner/advisor-leads"),
  insights: () => call<any>("/api/insights"),
};

export const inr = (n: number | null | undefined) =>
  n == null ? "" : "₹" + Math.round(n).toLocaleString("en-IN");
