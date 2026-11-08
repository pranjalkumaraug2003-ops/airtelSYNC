"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Bot, Mic, Send, Sparkles } from "lucide-react";
import { Badge, Button, Card, ErrorNote, Shell, Spinner } from "@/components/ui";
import { PlanCard } from "@/components/PlanCard";
import { api, type ChatResponse, type Recommendation } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { journey } from "@/lib/store";

type Msg = { role: "bot" | "me"; text: string };

const FIELD_LABEL: Record<string, string> = {
  business_type: "Business", employees: "Team size", sites: "Locations", city: "City", has_gstin: "GST", needs: "Needs",
};

export default function Advisor() {
  const { t, lang } = useI18n();
  const router = useRouter();
  const [sid, setSid] = useState<string | null>(null);
  const [mode, setMode] = useState<"ai" | "guided">("guided");
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [chips, setChips] = useState<string[]>([]);
  const [picked, setPicked] = useState<string[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [last, setLast] = useState<ChatResponse | null>(null);
  const [rec, setRec] = useState<Recommendation | null>(null);
  const [listening, setListening] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    setMsgs([]);
    setRec(null);
    setBusy(true);
    api.advisorStart(lang)
      .then((r) => {
        if (cancelled) return;
        setSid(r.session_id);
        journey.saveAdvisor(r.session_id);
        setMode(r.mode);
        setMsgs([{ role: "bot", text: r.reply }]);
        setChips(r.quick_replies);
        setLast(r);
      })
      .catch((e) => setError(`${e.message}. Is the backend running?`))
      .finally(() => setBusy(false));
    return () => {
      cancelled = true;
    };
  }, [lang]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs, rec]);

  const multi = last?.missing?.[0] === "needs";

  async function send(text: string, showPlan = false) {
    if (!sid || !text.trim() || busy) return;
    setError(null);
    setMsgs((m) => [...m, { role: "me", text }]);
    setInput("");
    setPicked([]);
    setBusy(true);
    try {
      const r = await api.advisorChat(sid, text, showPlan);
      setMode(r.mode);
      setLast(r);
      setMsgs((m) => [...m, { role: "bot", text: r.reply }]);
      setChips(r.quick_replies);
      if (r.recommendation) {
        setRec(r.recommendation);
        journey.saveRecommendation(r.recommendation);
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  function onChip(c: string) {
    if (rec) {
      if (/kyc|KYC/.test(c)) router.push("/kyc");
      else router.push("/quote");
      return;
    }
    if (multi) setPicked((p) => (p.includes(c) ? p.filter((x) => x !== c) : [...p, c]));
    else send(c);
  }

  function voice() {
    const SR: any = (typeof window !== "undefined" && ((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition)) || null;
    if (!SR) {
      setError("Voice input works in Chrome on Android and desktop.");
      return;
    }
    const r = new SR();
    r.lang = { hi: "hi-IN", ta: "ta-IN", te: "te-IN", mr: "mr-IN", bn: "bn-IN", gu: "gu-IN", kn: "kn-IN", ml: "ml-IN", pa: "pa-IN" }[lang] || "en-IN";
    r.onresult = (e: any) => setInput(e.results[0][0].transcript);
    r.onend = () => setListening(false);
    setListening(true);
    r.start();
  }

  const known = last?.profile;
  return (
    <Shell step={rec ? 1 : 0}>
      <div className="mb-3 flex items-center justify-between">
        <h1 className="text-lg font-bold">Udyam Saathi</h1>
        <Badge tone={mode === "ai" ? "brand" : "neutral"}>
          {mode === "ai" ? <Sparkles size={12} /> : <Bot size={12} />} {mode === "ai" ? t("ai_on") : t("ai_off")}
        </Badge>
      </div>

      {known && (
        <Card className="mb-3 py-3">
          <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-ink/40">{t("what_we_know")}</div>
          <div className="flex flex-wrap gap-1.5">
            {Object.keys(FIELD_LABEL).map((f) => {
              const v: any = f === "needs" ? (known.needs?.length ? known.needs.map((n) => n.replace(/_/g, " ")).join(", ") : null) : f === "has_gstin" ? (known.gstin ? "GSTIN " + known.gstin.slice(0, 2) + "…" : known.has_gstin == null ? null : known.has_gstin ? "Yes" : "No") : (known as any)[f];
              return (
                <Badge key={f} tone={v != null && v !== "" ? "pass" : "neutral"}>
                  {FIELD_LABEL[f]}: {v != null && v !== "" ? String(v) : "…"}
                </Badge>
              );
            })}
          </div>
        </Card>
      )}

      <div className="space-y-2.5" aria-live="polite">
        {msgs.map((m, i) => (
          <div key={i} className={m.role === "me" ? "flex justify-end" : "flex"}>
            <div className={m.role === "me" ? "max-w-[85%] rounded-2xl rounded-br-md bg-brand px-3.5 py-2.5 text-sm text-white" : "max-w-[85%] rounded-2xl rounded-bl-md bg-white px-3.5 py-2.5 text-sm shadow-soft"}>
              {m.text}
            </div>
          </div>
        ))}
        {busy && <div className="flex"><div className="rounded-2xl bg-white px-3.5 py-2.5 shadow-soft"><Spinner /></div></div>}
        {rec && <PlanCard rec={rec} onContinue={() => router.push("/quote")} />}
        <div ref={endRef} />
      </div>

      <ErrorNote error={error} />

      <div className="fixed inset-x-0 bottom-0 z-10 border-t border-ink/5 bg-white/95 backdrop-blur">
        <div className="mx-auto max-w-xl px-4 py-3">
          {chips.length > 0 && (
            <div className="mb-2 flex flex-wrap gap-1.5">
              {chips.map((c) => (
                <button key={c} onClick={() => onChip(c)} className={`rounded-full border px-3 py-1.5 text-xs font-medium ${picked.includes(c) ? "border-brand bg-brand text-white" : "border-ink/15 bg-white text-ink/80"}`}>
                  {c}
                </button>
              ))}
              {multi && picked.length > 0 && <Button className="min-h-0 py-1.5 text-xs" onClick={() => send(picked.join(", "))}>Done ({picked.length})</Button>}
            </div>
          )}
          <form onSubmit={(e) => { e.preventDefault(); send(input); }} className="flex gap-2">
            <input value={input} onChange={(e) => setInput(e.target.value)} placeholder={t("chat_placeholder")} aria-label="Message"
              className="min-h-[44px] flex-1 rounded-xl border border-ink/10 px-3 text-sm outline-none focus:border-brand" />
            <Button type="button" variant="outline" onClick={voice} aria-label="Speak" className={listening ? "border-brand text-brand" : ""}><Mic size={18} /></Button>
            <Button type="submit" aria-label={t("send")} disabled={busy || !input.trim()}><Send size={18} /></Button>
          </form>
          {!rec && last && last.profile.business_type && last.profile.needs?.length > 0 && (
            <button onClick={() => send(t("show_plan"), true)} className="mt-2 text-xs font-semibold text-brand">{t("show_plan")} →</button>
          )}
        </div>
      </div>
    </Shell>
  );
}
