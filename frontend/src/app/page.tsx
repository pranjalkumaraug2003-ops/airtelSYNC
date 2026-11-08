"use client";
import Link from "next/link";
import { ArrowRight, BadgeCheck, FileCheck2, MessageCircle, ReceiptIndianRupee, Truck } from "lucide-react";
import { Card, Shell } from "@/components/ui";
import { useI18n } from "@/lib/i18n";

export default function Home() {
  const { t } = useI18n();
  const steps = [
    { icon: MessageCircle, title: t("step_advisor"), sub: t("sub_advisor") },
    { icon: ReceiptIndianRupee, title: t("step_quote"), sub: t("sub_quote") },
    { icon: FileCheck2, title: t("step_kyc"), sub: t("sub_kyc") },
    { icon: Truck, title: t("step_track"), sub: t("sub_track") },
  ];
  return (
    <Shell>
      <section className="rounded-3xl bg-ink px-5 py-7 text-white">
        <span className="inline-flex items-center gap-1 rounded-full bg-white/10 px-3 py-1 text-xs font-medium">
          <BadgeCheck size={14} /> {t("audience")}
        </span>
        <h1 className="mt-4 text-[28px] font-extrabold leading-tight">{t("hero")}</h1>
        <p className="mt-2 text-sm text-white/70">{t("tagline")}</p>
        <Link href="/advisor" className="mt-6 flex min-h-[48px] items-center justify-center gap-2 rounded-xl bg-brand font-semibold">
          {t("start")} <ArrowRight size={18} />
        </Link>
        <div className="mt-3 grid grid-cols-2 gap-2 text-center text-sm">
          <Link href="/track" className="rounded-xl bg-white/10 py-3 font-medium">{t("track")}</Link>
          <Link href="/partner" className="rounded-xl bg-white/10 py-3 font-medium">{t("partner")}</Link>
        </div>
      </section>

      <div className="mt-5 grid gap-3">
        {steps.map((s, i) => (
          <Card key={i} className="flex items-center gap-3">
            <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-brand/10 text-brand"><s.icon size={20} /></span>
            <div>
              <div className="text-sm font-semibold">{i + 1}. {s.title}</div>
              <div className="text-xs text-ink/50">{s.sub}</div>
            </div>
          </Card>
        ))}
      </div>

      <Card className="mt-5">
        <div className="grid grid-cols-3 divide-x divide-ink/5 text-center">
          <div><div className="text-xl font-extrabold text-brand">10 min</div><div className="text-[11px] text-ink/50">to a confirmed order</div></div>
          <div><div className="text-xl font-extrabold text-brand">1 bill</div><div className="text-[11px] text-ink/50">for every service</div></div>
          <div><div className="text-xl font-extrabold text-brand">10</div><div className="text-[11px] text-ink/50">Indian languages</div></div>
        </div>
      </Card>
      <p className="mt-6 text-center text-[11px] text-ink/40">Prototype for Airtel SYNC 2026 · Team 2Pointers, DTU · fictional operator and synthetic data</p>
    </Shell>
  );
}
