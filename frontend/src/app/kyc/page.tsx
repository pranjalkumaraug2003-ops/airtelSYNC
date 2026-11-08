"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, Camera, CheckCircle2, FileSearch, ShieldCheck, Trash2, XCircle } from "lucide-react";
import { Badge, Button, Card, ErrorNote, Shell, Spinner } from "@/components/ui";
import { api, type KycReport } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { journey } from "@/lib/store";

type Notice = Awaited<ReturnType<typeof api.notice>>;
const SAMPLES = ["K01", "K02", "K03", "K04", "K05", "K06", "K07", "K08", "K09", "K10", "K11", "K12"];
const SLOTS = ["Tomorrow 10am-1pm", "Tomorrow 2pm-6pm", "Day after 10am-1pm", "This Sunday 10am-1pm"];

export default function Kyc() {
  const { t, lang } = useI18n();
  const router = useRouter();
  const [notice, setNotice] = useState<Notice | null>(null);
  const [purposes, setPurposes] = useState<Record<string, boolean>>({ kyc_verification: true, service_activation: true, order_updates: true });
  const [sid, setSid] = useState<string | null>(null);
  const [gstin, setGstin] = useState("");
  const [lookup, setLookup] = useState<any>(null);
  const [docs, setDocs] = useState<Record<string, any>>({});
  const [report, setReport] = useState<KycReport | null>(null);
  const [phone, setPhone] = useState("");
  const [slot, setSlot] = useState(SLOTS[0]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.notice(lang).then(setNotice).catch((e) => setError(e.message));
    setSid(journey.kyc());
  }, [lang]);

  async function run<T>(label: string, f: () => Promise<T>) {
    setBusy(label);
    setError(null);
    try {
      return await f();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(null);
    }
  }

  const consent = () => run("consent", async () => {
    const r = await api.consent(lang, Object.keys(purposes).filter((k) => purposes[k]));
    setSid(r.session_id);
    journey.saveKyc(r.session_id);
  });

  const doLookup = () => run("lookup", async () => {
    const g = gstin.trim().toUpperCase();
    const r = await api.gstin(g);
    setLookup(r);
    if (r.found && sid) await api.declareGstin(sid, g);
  });

  const upload = (type: string, file: File) => run(type, async () => {
    const r = await api.upload(sid!, type, file);
    setDocs((d) => ({ ...d, [type]: r }));
    setReport(null);
  });

  const sample = (k: string) => run("sample", async () => {
    const r = await api.sample(sid!, k);
    setLookup(null);
    setGstin("");
    setDocs(Object.fromEntries(r.loaded.map((d: any) => [d.doc_type, d])));
    setReport(await api.report(sid!));
  });

  const check = () => run("check", async () => setReport(await api.report(sid!)));

  const order = () => run("order", async () => {
    const rec = journey.recommendation();
    if (!rec) throw new Error("No plan in this session. Start with the advisor.");
    const o = await api.createOrder({ profile: rec.profile, items: journey.items() || rec.quote.items, kyc_session_id: sid!, contact_phone: phone, preferred_slot: slot });
    router.push(`/track/${o.id}`);
  });

  const withdraw = () => run("withdraw", async () => {
    if (sid) await api.withdraw(sid);
    journey.saveKyc(null);
    setSid(null);
    setDocs({});
    setReport(null);
    setLookup(null);
  });

  const icon = (s: string) => (s === "pass" ? <CheckCircle2 size={16} className="text-emerald-600" /> : s === "warn" ? <AlertTriangle size={16} className="text-amber-600" /> : <XCircle size={16} className="text-rose-600" />);

  return (
    <Shell step={2}>
      {!sid && notice && (
        <Card>
          <div className="flex items-center gap-2 text-base font-bold"><ShieldCheck className="text-brand" size={20} /> {notice.title}</div>
          <ul className="mt-3 space-y-2 text-sm text-ink/75">
            {notice.points.map((p, i) => <li key={i} className="flex gap-2"><span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand" />{p}</li>)}
          </ul>
          <div className="mt-4 space-y-2">
            {Object.entries(notice.purposes).map(([k, v]) => (
              <label key={k} className="flex items-start gap-2 rounded-xl border border-ink/10 p-3 text-sm">
                <input type="checkbox" className="mt-0.5 h-4 w-4 accent-brand" checked={!!purposes[k]} disabled={k === "kyc_verification"}
                  onChange={(e) => setPurposes((p) => ({ ...p, [k]: e.target.checked }))} />
                <span>{v}{k === "kyc_verification" && <Badge tone="neutral">required</Badge>}</span>
              </label>
            ))}
          </div>
          <Button className="mt-4 w-full" onClick={consent} disabled={busy === "consent"}>{busy === "consent" ? <Spinner /> : t("consent_continue")}</Button>
        </Card>
      )}

      {sid && (
        <>
          <Card>
            <div className="text-sm font-semibold">{t("gstin_lookup")}</div>
            <div className="mt-2 flex gap-2">
              <input value={gstin} onChange={(e) => setGstin(e.target.value.toUpperCase())} maxLength={15} placeholder="e.g. 37NBLXS1145E1ZU" aria-label="GSTIN"
                className="min-h-[44px] flex-1 rounded-xl border border-ink/10 px-3 font-mono text-sm uppercase outline-none focus:border-brand" />
              <Button variant="outline" onClick={doLookup} disabled={gstin.length !== 15 || busy === "lookup"}>{busy === "lookup" ? <Spinner /> : t("lookup")}</Button>
            </div>
            {lookup && (lookup.found ? (
              <div className="mt-3 rounded-xl bg-sand p-3 text-sm">
                <div className="flex items-center justify-between"><b>{lookup.trade_name}</b><Badge tone={lookup.status === "Active" ? "pass" : "fail"}>GST {lookup.status}</Badge></div>
                <div className="text-xs text-ink/60">{lookup.legal_name} · {lookup.constitution} · since {lookup.registration_date}</div>
                <div className="text-xs text-ink/60">{lookup.address}</div>
              </div>
            ) : <p className="mt-2 text-sm text-rose-700">{lookup.errors?.join(". ")}</p>)}
          </Card>

          <Card className="mt-3">
            <div className="text-sm font-semibold">{t("upload_docs")}</div>
            <p className="text-xs text-ink/50">Photos are read on our server and deleted after 30 minutes.</p>
            <div className="mt-3 grid gap-2">
              {notice?.required_documents.map((d) => {
                const got = docs[d.type];
                return (
                  <label key={d.type} className="flex cursor-pointer items-center gap-3 rounded-xl border border-dashed border-ink/15 p-3">
                    <span className="grid h-9 w-9 place-items-center rounded-lg bg-brand/10 text-brand">{busy === d.type ? <Spinner /> : <Camera size={18} />}</span>
                    <span className="flex-1 text-sm">
                      <span className="font-medium">{d.label}</span>
                      {got && <span className="block text-xs text-ink/55">{got.quality?.is_blurry ? "Too blurred to read" : Object.entries(got.fields || {}).filter(([k, v]) => v && typeof v === "string" && !k.endsWith("_raw")).slice(0, 2).map(([, v]) => v).join(" · ")}</span>}
                    </span>
                    {got && <Badge tone={got.quality?.is_blurry ? "fail" : "pass"}>{got.quality?.is_blurry ? "retake" : "read"}</Badge>}
                    <input type="file" accept="image/*" capture="environment" className="sr-only" onChange={(e) => e.target.files?.[0] && upload(d.type, e.target.files[0])} />
                  </label>
                );
              })}
            </div>
            <div className="mt-3 flex items-center gap-2">
              <span className="text-xs text-ink/50">{t("try_sample")}</span>
              <select aria-label="Sample applicant" className="rounded-lg border border-ink/10 px-2 py-1 text-xs" defaultValue="" onChange={(e) => e.target.value && sample(e.target.value)}>
                <option value="" disabled>K01-K12</option>
                {SAMPLES.map((k) => <option key={k} value={k}>{k}</option>)}
              </select>
              {busy === "sample" && <Spinner />}
            </div>
            <Button className="mt-3 w-full" variant="outline" onClick={check} disabled={!Object.keys(docs).length || busy === "check"}>
              {busy === "check" ? <Spinner /> : <FileSearch size={16} />} {t("check_docs")}
            </Button>
          </Card>

          {report && (
            <Card className="mt-3">
              <div className="flex items-center justify-between">
                <div className="text-base font-bold">{report.verdict === "verified" ? t("verified") : t("needs_action")}</div>
                <Badge tone={report.verdict === "verified" ? "pass" : "fail"}><span className="whitespace-nowrap">{report.summary.pass} ✓ · {report.summary.fail} ✗ · {report.summary.warn} !</span></Badge>
              </div>
              {report.business_name && <div className="text-xs text-ink/50">{report.business_name} {report.gstin_masked && `· GSTIN ${report.gstin_masked}`}</div>}
              <ul className="mt-3 space-y-2">
                {[...report.checks].sort((a, b) => ["fail", "warn", "pass"].indexOf(a.status) - ["fail", "warn", "pass"].indexOf(b.status)).map((c) => (
                  <li key={c.id} className="flex gap-2 text-sm">
                    <span className="mt-0.5">{icon(c.status)}</span>
                    <span>
                      <span className="font-medium">{c.title}</span>
                      <span className="block text-xs text-ink/60">{c.detail}</span>
                      {c.fix && c.status !== "pass" && <span className="block text-xs font-medium text-brand">→ {c.fix}</span>}
                    </span>
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {report && (
            <Card className="mt-3">
              <label className="block text-sm font-medium">{t("phone")}
                <input value={phone} onChange={(e) => setPhone(e.target.value.replace(/\D/g, "").slice(0, 10))} inputMode="numeric" placeholder="98XXXXXXXX"
                  className="mt-1 min-h-[44px] w-full rounded-xl border border-ink/10 px-3 text-sm outline-none focus:border-brand" />
              </label>
              <label className="mt-3 block text-sm font-medium">{t("slot")}
                <select value={slot} onChange={(e) => setSlot(e.target.value)} className="mt-1 min-h-[44px] w-full rounded-xl border border-ink/10 px-3 text-sm">
                  {SLOTS.map((s) => <option key={s}>{s}</option>)}
                </select>
              </label>
              <Button className="mt-4 w-full" onClick={order} disabled={busy === "order" || phone.length !== 10}>{busy === "order" ? <Spinner /> : t("place_order")}</Button>
              {report.verdict !== "verified" && <p className="mt-2 text-xs text-ink/55">You can place the order now; activation starts once the items above are fixed.</p>}
            </Card>
          )}

          <Button variant="ghost" className="mt-4 w-full text-xs" onClick={withdraw}><Trash2 size={14} /> {t("delete_data")}</Button>
        </>
      )}
      <ErrorNote error={error} />
    </Shell>
  );
}
