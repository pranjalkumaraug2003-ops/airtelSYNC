"use client";
import { useEffect, useState } from "react";
import clsx from "clsx";
import { ArrowDownRight, ArrowUpRight, PhoneCall, Sparkles } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Badge, Card, ErrorNote, Shell, Spinner } from "@/components/ui";
import { api, inr } from "@/lib/api";

const TABS = ["Call list", "Advisor hand-offs", "Insights"] as const;

export default function Partner() {
  const [tab, setTab] = useState<(typeof TABS)[number]>("Call list");
  const [calls, setCalls] = useState<{ model: any; leads: any[] } | null>(null);
  const [handoffs, setHandoffs] = useState<any[] | null>(null);
  const [ins, setIns] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.callList(25).then(setCalls).catch((e) => setError(e.message));
    api.advisorLeads().then(setHandoffs).catch(() => setHandoffs([]));
    api.insights().then(setIns).catch((e) => setError(e.message));
  }, []);

  return (
    <Shell wide>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold">Partner & field console</h1>
          <p className="text-sm text-ink/55">Leads the digital journey could not close, ranked by how likely they are to convert. Partners earn commission on digital sales they assist.</p>
        </div>
        <div className="flex rounded-xl bg-white p-1 shadow-soft">
          {TABS.map((t) => (
            <button key={t} onClick={() => setTab(t)} className={clsx("rounded-lg px-3 py-2 text-sm font-medium", tab === t ? "bg-ink text-white" : "text-ink/60")}>{t}</button>
          ))}
        </div>
      </div>
      <ErrorNote error={error} />

      {tab === "Call list" && (
        <div className="mt-4">
          {calls && (
            <div className="mb-3 grid gap-3 sm:grid-cols-3">
              <Stat label="Model accuracy (AUC, 5-fold)" value={calls.model.auc.toFixed(2)} />
              <Stat label="Conversion in top 20% of scores" value={`${(calls.model.top20_activation_rate * 100).toFixed(1)}%`} sub={`vs ${(calls.model.base_rate * 100).toFixed(1)}% overall`} />
              <Stat label="Activations found in top 20%" value={`${Math.round(calls.model.top20_share_of_activations * 100)}%`} />
            </div>
          )}
          {!calls ? <Spinner /> : (
            <Card className="overflow-x-auto p-0">
              <table className="w-full min-w-[780px] text-sm">
                <thead className="bg-sand text-left text-[11px] uppercase tracking-wide text-ink/50">
                  <tr><th className="p-3">Business</th><th className="p-3">Dropped because</th><th className="p-3">Score</th><th className="p-3">Why</th><th className="p-3">Next action</th></tr>
                </thead>
                <tbody>
                  {calls.leads.map((l) => (
                    <tr key={l.lead_id} className="border-t border-ink/5 align-top">
                      <td className="p-3"><div className="font-semibold">{l.business_name}</div><div className="text-xs text-ink/50">{l.business_type} · {l.city} · {l.language} · {l.source}</div></td>
                      <td className="p-3 text-xs">{l.drop_reason}<div className="text-ink/40">at {l.stage_reached}</div></td>
                      <td className="p-3"><ScoreBar v={l.score} /></td>
                      <td className="p-3 text-xs">{l.why.map((w: any, i: number) => (
                        <div key={i} className="flex items-center gap-1">{w.effect === "up" ? <ArrowUpRight size={12} className="text-emerald-600" /> : <ArrowDownRight size={12} className="text-rose-600" />}{w.factor}</div>
                      ))}</td>
                      <td className="p-3"><span className="inline-flex items-center gap-1 rounded-lg bg-brand/10 px-2 py-1 text-xs font-medium text-brand"><PhoneCall size={12} />{l.next_action}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          )}
        </div>
      )}

      {tab === "Advisor hand-offs" && (
        <div className="mt-4">
          {!handoffs ? <Spinner /> : handoffs.length === 0 ? (
            <Card className="text-sm text-ink/60">No open advisor conversations yet. Owners who get a plan but don't order appear here with a score, so a partner can call in their language.</Card>
          ) : (
            <div className="grid gap-3 md:grid-cols-2">
              {handoffs.map((h) => (
                <Card key={h.session_id}>
                  <div className="flex items-center justify-between"><b>{h.business}</b><Badge tone="brand"><Sparkles size={12} /> {h.stage}</Badge></div>
                  <div className="text-xs text-ink/50">{h.city || "City not given"} · {h.language}{h.monthly_value ? ` · plan ${inr(h.monthly_value)}/mo` : ""}</div>
                  <div className="mt-2"><ScoreBar v={h.score} /></div>
                  {h.missing.length > 0 && <div className="mt-2 text-xs text-ink/60">Still needs: {h.missing.join(", ")}</div>}
                </Card>
              ))}
            </div>
          )}
        </div>
      )}

      {tab === "Insights" && ins && (
        <div className="mt-4 grid gap-3 lg:grid-cols-2">
          <div className="grid grid-cols-2 gap-3 lg:col-span-2 lg:grid-cols-4">
            <Stat label="Lead to activation" value={`${ins.headline.conversion}%`} sub={`${ins.headline.activations} of ${ins.headline.leads.toLocaleString("en-IN")}`} />
            <Stat label="Days to activate" value={ins.headline.avg_days_to_activate} sub={`${ins.headline.avg_status_chases} status chases`} />
            <Stat label="Cost per activation" value={inr(ins.headline.cac_per_activation)} sub={`${ins.headline.spend_on_dropped_share}% spent on drop-offs`} />
            <Stat label="Bundles breaking catalogue rules" value={ins.rule_violations_in_sold_bundles} sub={`${ins.activated_on_inactive_gstin} on cancelled/suspended GSTIN`} />
          </div>
          <Card>
            <div className="mb-2 text-sm font-semibold">Funnel, Apr-Jun 2026</div>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={ins.funnel} layout="vertical" margin={{ left: 30, right: 40 }}>
                <XAxis type="number" hide /><YAxis type="category" dataKey="stage" width={110} tick={{ fontSize: 12 }} />
                <Tooltip /><Bar dataKey="count" fill="#D7192A" radius={[0, 6, 6, 0]}><LabelList dataKey="count" position="right" fontSize={12} /></Bar>
              </BarChart>
            </ResponsiveContainer>
          </Card>
          <Card>
            <div className="mb-2 text-sm font-semibold">6-month churn rises with every status chase</div>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={ins.status_chasing}>
                <CartesianGrid vertical={false} stroke="#eee" /><XAxis dataKey="band" tick={{ fontSize: 12 }} /><YAxis unit="%" tick={{ fontSize: 12 }} />
                <Tooltip /><Bar dataKey="churn_6m" radius={[6, 6, 0, 0]}>{ins.status_chasing.map((_: any, i: number) => <Cell key={i} fill={["#94a3b8", "#f59e0b", "#D7192A"][i]} />)}<LabelList dataKey="churn_6m" position="top" formatter={(v: any) => `${v}%`} fontSize={12} /></Bar>
              </BarChart>
            </ResponsiveContainer>
          </Card>
          <Card className="overflow-x-auto lg:col-span-2">
            <div className="mb-2 text-sm font-semibold">Segment economics</div>
            <table className="w-full min-w-[640px] text-sm">
              <thead className="text-left text-[11px] uppercase tracking-wide text-ink/50"><tr><th className="py-2">Segment</th><th>Share of leads</th><th>Activation</th><th>Median bundle</th><th>Cost / activation</th><th>Payback</th><th>6-mo churn</th></tr></thead>
              <tbody>{ins.segments.map((s: any) => (
                <tr key={s.key} className="border-t border-ink/5"><td className="py-2 font-medium">{s.segment}</td><td>{s.share}%</td><td>{s.activation_rate}%</td><td>{inr(s.median_bundle)}</td><td>{inr(s.cac_per_activation)}</td><td>{s.payback_months} mo</td><td>{s.churn_6m}%</td></tr>
              ))}</tbody>
            </table>
          </Card>
        </div>
      )}
    </Shell>
  );
}

function Stat({ label, value, sub }: { label: string; value: any; sub?: string }) {
  return (
    <Card className="py-3">
      <div className="text-[11px] text-ink/50">{label}</div>
      <div className="text-2xl font-extrabold tabular-nums">{value}</div>
      {sub && <div className="text-[11px] text-ink/50">{sub}</div>}
    </Card>
  );
}

function ScoreBar({ v }: { v: number }) {
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 w-20 rounded-full bg-ink/10"><div className="h-2 rounded-full bg-brand" style={{ width: `${Math.round(v * 100)}%` }} /></div>
      <span className="text-xs font-semibold tabular-nums">{Math.round(v * 100)}</span>
    </div>
  );
}
