"use client";
import { CheckCircle2, Clock, Lock } from "lucide-react";
import { Button, Card } from "./ui";
import { inr, type Recommendation } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

export function PlanCard({ rec, onContinue }: { rec: Recommendation; onContinue: () => void }) {
  const { t } = useI18n();
  const q = rec.quote;
  const sel = q.items.filter((i) => i.selected);
  return (
    <Card className="border-brand/20">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-brand">{t("your_plan")} · {rec.segment_label}</div>
      <div className="mt-1 flex items-baseline gap-1">
        <span className="text-3xl font-extrabold tabular-nums">{inr(q.monthly_total)}</span>
        <span className="text-sm text-ink/50">{t("per_month")} {t("plus_gst")}</span>
      </div>
      <div className="mt-1 flex flex-wrap gap-x-3 text-xs text-ink/60">
        <span>{t("setup")}: {inr(q.one_time_setup)}</span>
        <span>{t("contract")}: {q.contract_months} {t("months")}</span>
        <span className="inline-flex items-center gap-1"><Clock size={12} /> {t("activation")} {q.expected_activation_days} {t("days")}</span>
      </div>
      <ul className="mt-3 space-y-2">
        {sel.map((i) => (
          <li key={i.product_id} className="flex gap-2 text-sm">
            <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-emerald-600" />
            <span>
              <span className="font-semibold">{i.name}{i.quantity > 1 ? ` × ${i.quantity}` : ""}</span>
              <span className="text-ink/50"> · {inr(i.monthly)}</span>
              <span className="block text-xs text-ink/55">{i.reason}</span>
            </span>
          </li>
        ))}
        {q.excluded.map((e) => (
          <li key={e.product_id} className="flex gap-2 text-sm text-ink/50">
            <Lock size={16} className="mt-0.5 shrink-0" />
            <span><span className="font-medium">{e.name}</span><span className="block text-xs">{e.reason}. {e.unlock}.</span></span>
          </li>
        ))}
      </ul>
      {q.notes.length > 0 && <p className="mt-3 rounded-xl bg-sand px-3 py-2 text-xs text-ink/70">{q.notes.join(" ")}</p>}
      <Button className="mt-4 w-full" onClick={onContinue}>{t("customise")}</Button>
    </Card>
  );
}
