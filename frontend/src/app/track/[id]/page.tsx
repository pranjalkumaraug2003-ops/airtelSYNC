"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { CheckCircle2, Circle, MessageCircle, PlayCircle } from "lucide-react";
import { Badge, Button, Card, ErrorNote, Shell, Spinner } from "@/components/ui";
import { api, inr, type OrderView } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

export default function Track() {
  // Next 15: read route params with useParams() in client components.
  const params = useParams<{ id: string }>();
  const { t } = useI18n();
  const [o, setO] = useState<OrderView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.order(params.id).then(setO).catch((e) => setError(e.message));
  }, [params.id]);

  async function advance() {
    setBusy(true);
    try {
      setO(await api.advance(params.id));
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  const fmt = (s: string) => new Date(s).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

  return (
    <Shell step={3}>
      <ErrorNote error={error} />
      {!o && !error && <Spinner />}
      {o && (
        <>
          <Card>
            <div className="text-[11px] font-semibold uppercase tracking-wide text-ink/40">{t("order_code")}</div>
            <div className="flex items-center justify-between">
              <div className="font-mono text-xl font-bold">{o.id}</div>
              <Badge tone={o.kyc_verdict === "verified" ? "pass" : "warn"}>KYC {o.kyc_verdict.replace("_", " ")}</Badge>
            </div>
            <div className="mt-1 text-sm">{o.business_name}</div>
            <div className="mt-2 grid grid-cols-2 gap-2 text-sm">
              <div className="rounded-xl bg-sand p-2.5"><div className="text-[11px] text-ink/50">{t("expected")}</div><div className="font-bold">{new Date(o.expected_activation).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}</div></div>
              <div className="rounded-xl bg-sand p-2.5"><div className="text-[11px] text-ink/50">{t("total")}</div><div className="font-bold tabular-nums">{inr(o.monthly_total)}</div></div>
            </div>
          </Card>

          <Card className="mt-3">
            <ol className="relative ml-2 border-l-2 border-ink/10">
              {o.timeline.map((s) => (
                <li key={s.key} className="mb-4 ml-4 last:mb-0">
                  <span className="absolute -left-[11px] bg-white">{s.done ? <CheckCircle2 size={20} className="text-emerald-600" /> : <Circle size={20} className={s.current ? "text-brand" : "text-ink/20"} />}</span>
                  <div className={`text-sm font-semibold ${s.done ? "" : s.current ? "text-brand" : "text-ink/40"}`}>{s.title}</div>
                  <div className="text-xs text-ink/50">{s.description}{s.at ? ` · ${fmt(s.at)}` : ""}</div>
                </li>
              ))}
            </ol>
          </Card>

          <Card className="mt-3">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-ink/40">Services</div>
            {o.lines.map((l) => (
              <div key={l.product_id} className="flex items-center justify-between py-1.5 text-sm">
                <span>{l.name}{l.quantity > 1 ? ` × ${l.quantity}` : ""}</span>
                <Badge tone={l.status === "active" ? "pass" : "neutral"}>{l.status === "active" ? "Active" : `by ${new Date(l.expected_by).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}`}</Badge>
              </div>
            ))}
          </Card>

          <Card className="mt-3">
            <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-ink/40"><MessageCircle size={13} /> {t("updates")} {o.contact_phone_masked && `· ${o.contact_phone_masked}`}</div>
            <ul className="mt-2 space-y-2">
              {[...o.notifications].reverse().map((n, i) => (
                <li key={i} className="rounded-xl bg-emerald-50 px-3 py-2 text-xs text-emerald-900"><b className="font-semibold">WhatsApp · {fmt(n.at)}</b><br />{n.message}</li>
              ))}
            </ul>
          </Card>

          {o.stage_index < 4 && (
            <Button variant="outline" className="mt-4 w-full" onClick={advance} disabled={busy}>{busy ? <Spinner /> : <PlayCircle size={16} />} {t("simulate")}</Button>
          )}
        </>
      )}
    </Shell>
  );
}
