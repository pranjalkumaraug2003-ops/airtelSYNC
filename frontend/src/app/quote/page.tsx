"use client";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Lock, ShieldCheck } from "lucide-react";
import { Badge, Button, Card, ErrorNote, Shell, Spinner, Stepper, Switch } from "@/components/ui";
import { api, inr, type LineItem, type Quote, type Recommendation } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { journey } from "@/lib/store";

const PER_UNIT_EDITABLE = new Set(["per line", "per user", "per camera", "per counter", "per device", "per vehicle", "per channel"]);

export default function QuotePage() {
  const { t } = useI18n();
  const router = useRouter();
  const [rec, setRec] = useState<Recommendation | null>(null);
  const [quote, setQuote] = useState<Quote | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const r = journey.recommendation();
    if (!r) return;
    setRec(r);
    const items = journey.items() || r.quote.items;
    setQuote({ ...r.quote, items });
  }, []);

  async function update(toggles: Record<string, boolean>, quantities: Record<string, number>) {
    if (!rec || !quote) return;
    setBusy(true);
    setError(null);
    try {
      const q = await api.requote(rec.profile, quote.items, toggles, quantities);
      setQuote(q);
      journey.saveItems(q.items);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  const [core, optional] = useMemo(() => {
    const items = quote?.items || [];
    return [items.filter((i) => i.core || (i.selected && !i.reason.startsWith("Optional"))), items.filter((i) => !i.core && (!i.selected || i.reason.startsWith("Optional")))];
  }, [quote]);

  if (!rec || !quote) {
    return (
      <Shell step={1}>
        <Card>No plan yet. <Link className="font-semibold text-brand" href="/advisor">Start with the advisor →</Link></Card>
      </Shell>
    );
  }

  const Row = ({ i, toggle }: { i: LineItem; toggle: boolean }) => (
    <div className="flex items-start gap-3 py-3">
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-1.5 text-sm font-semibold">
          {i.name}
          {i.auto_added_for && <Badge tone="neutral">required</Badge>}
        </div>
        <div className="text-xs text-ink/55">{i.reason}</div>
        <div className="mt-1 text-xs text-ink/70 tabular-nums">
          {inr(i.unit_price)} {i.unit} {i.setup_fee > 0 && `· setup ${inr(i.setup_fee)}`} · {i.min_contract_months} mo min
        </div>
      </div>
      <div className="flex flex-col items-end gap-2">
        <span className="text-sm font-bold tabular-nums">{inr(i.monthly)}</span>
        {PER_UNIT_EDITABLE.has(i.unit) && i.selected && (
          <Stepper label={i.name} value={i.quantity} onChange={(v) => update({}, { [i.product_id]: v })} />
        )}
        {toggle && <Switch label={i.name} checked={i.selected} onChange={(v) => update({ [i.product_id]: v }, {})} />}
      </div>
    </div>
  );

  return (
    <Shell step={1}>
      <h1 className="text-lg font-bold">{rec.profile.business_name || rec.profile.business_type}</h1>
      <p className="text-xs text-ink/50">{rec.segment_label}{rec.profile.city ? ` · ${rec.profile.city}` : ""}</p>

      <Card className="mt-4">
        <div className="text-[11px] font-semibold uppercase tracking-wide text-ink/40">{t("included")}</div>
        <div className="divide-y divide-ink/5">{core.map((i) => <Row key={i.product_id} i={i} toggle={!i.core} />)}</div>
      </Card>

      {optional.length > 0 && (
        <Card className="mt-3">
          <div className="text-[11px] font-semibold uppercase tracking-wide text-ink/40">{t("addons")}</div>
          <div className="divide-y divide-ink/5">{optional.map((i) => <Row key={i.product_id} i={i} toggle />)}</div>
        </Card>
      )}

      {quote.excluded.length > 0 && (
        <Card className="mt-3">
          <div className="text-[11px] font-semibold uppercase tracking-wide text-ink/40">{t("held_back")}</div>
          {quote.excluded.map((e) => (
            <div key={e.product_id} className="flex gap-2 py-2 text-sm text-ink/60">
              <Lock size={16} className="mt-0.5 shrink-0" />
              <span><b className="font-semibold">{e.name}</b>: {e.reason}. <span className="text-brand">{e.unlock}</span></span>
            </div>
          ))}
        </Card>
      )}

      <ErrorNote error={error} />

      <div className="fixed inset-x-0 bottom-0 z-10 border-t border-ink/5 bg-white">
        <div className="mx-auto flex max-w-xl items-center gap-3 px-4 py-3">
          <div className="min-w-0 flex-1">
            <div className="text-[11px] text-ink/50">{t("total")} {busy && <Spinner />}</div>
            <div className="whitespace-nowrap text-xl font-extrabold tabular-nums">{inr(quote.monthly_total)}<span className="text-xs font-medium text-ink/50">{t("per_month")} + GST</span></div>
            <div className="truncate text-[11px] text-ink/50 tabular-nums">
              Setup {inr(quote.one_time_setup)} · {quote.contract_months} mo · live in ~{quote.expected_activation_days} days
            </div>
          </div>
          <Button onClick={() => router.push("/kyc")} disabled={busy} aria-label={t("continue_kyc")} className="shrink-0"><ShieldCheck size={16} /> {t("continue_short")}</Button>
        </div>
        {quote.notes.length > 0 && <div className="mx-auto max-w-xl px-4 pb-2 text-[11px] text-emerald-700">{quote.notes.join(" ")}</div>}
      </div>
    </Shell>
  );
}
