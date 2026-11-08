// Journey state kept in sessionStorage (cleared when the tab closes).
import type { BusinessProfile, LineItem, Recommendation } from "./api";

const K = { rec: "ud_rec", items: "ud_items", kyc: "ud_kyc", advisor: "ud_advisor" };

function read<T>(key: string): T | null {
  try {
    const v = sessionStorage.getItem(key);
    return v ? (JSON.parse(v) as T) : null;
  } catch {
    return null;
  }
}

function write(key: string, value: unknown) {
  try {
    sessionStorage.setItem(key, JSON.stringify(value));
  } catch {}
}

export const journey = {
  saveRecommendation: (r: Recommendation) => {
    write(K.rec, r);
    write(K.items, r.quote.items);
  },
  recommendation: () => read<Recommendation>(K.rec),
  profile: () => read<Recommendation>(K.rec)?.profile as BusinessProfile | undefined,
  saveItems: (items: LineItem[]) => write(K.items, items),
  items: () => read<LineItem[]>(K.items),
  saveKyc: (sid: string | null) => (sid ? write(K.kyc, sid) : sessionStorage.removeItem(K.kyc)),
  kyc: () => read<string>(K.kyc),
  saveAdvisor: (sid: string) => write(K.advisor, sid),
  advisor: () => read<string>(K.advisor),
};
