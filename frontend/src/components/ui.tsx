"use client";
import clsx from "clsx";
import Link from "next/link";
import { Globe, Store } from "lucide-react";
import { LANGS, useI18n } from "@/lib/i18n";

export function Shell({ children, wide = false, step }: { children: React.ReactNode; wide?: boolean; step?: number }) {
  const { lang, setLang } = useI18n();
  return (
    <div className="min-h-screen bg-sand">
      <header className="sticky top-0 z-20 border-b border-ink/5 bg-white/90 backdrop-blur">
        <div className={clsx("mx-auto flex items-center justify-between px-4 py-3", wide ? "max-w-6xl" : "max-w-xl")}>
          <Link href="/" className="flex items-center gap-2">
            <span className="grid h-8 w-8 place-items-center rounded-xl bg-brand text-white">
              <Store size={18} />
            </span>
            <span className="leading-tight">
              <span className="block text-sm font-bold text-ink">Accel Business</span>
              <span className="block text-[11px] font-medium text-ink/50">Udyam Digital</span>
            </span>
          </Link>
          <label className="flex items-center gap-1 rounded-full border border-ink/10 px-2 py-1 text-xs text-ink/70">
            <Globe size={14} />
            <select aria-label="Language" value={lang} onChange={(e) => setLang(e.target.value)} className="bg-transparent outline-none">
              {Object.entries(LANGS).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
          </label>
        </div>
        {step !== undefined && <Progress step={step} wide={wide} />}
      </header>
      <main className={clsx("mx-auto px-4 pb-24 pt-5", wide ? "max-w-6xl" : "max-w-xl")}>{children}</main>
    </div>
  );
}

function Progress({ step, wide }: { step: number; wide: boolean }) {
  const labels = ["Advisor", "Plan", "Verify", "Track"];
  return (
    <div className={clsx("mx-auto flex gap-1.5 px-4 pb-3", wide ? "max-w-6xl" : "max-w-xl")}>
      {labels.map((l, i) => (
        <div key={l} className="flex-1">
          <div className={clsx("h-1.5 rounded-full", i <= step ? "bg-brand" : "bg-ink/10")} />
          <div className={clsx("mt-1 text-[10px] font-semibold uppercase tracking-wide", i <= step ? "text-brand" : "text-ink/40")}>{l}</div>
        </div>
      ))}
    </div>
  );
}

export function Card({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={clsx("rounded-2xl border border-ink/5 bg-white p-4 shadow-soft", className)}>{children}</div>;
}

export function Button({ children, variant = "primary", className, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" | "outline" }) {
  return (
    <button
      {...props}
      className={clsx(
        "inline-flex min-h-[44px] items-center justify-center gap-2 rounded-xl px-4 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50",
        variant === "primary" && "bg-brand text-white hover:bg-brand-dark",
        variant === "outline" && "border border-ink/15 bg-white text-ink hover:border-ink/30",
        variant === "ghost" && "text-ink/70 hover:bg-ink/5",
        className,
      )}
    >
      {children}
    </button>
  );
}

export function Badge({ tone = "neutral", children }: { tone?: "pass" | "warn" | "fail" | "neutral" | "brand"; children: React.ReactNode }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold",
        tone === "pass" && "bg-emerald-50 text-emerald-700",
        tone === "warn" && "bg-amber-50 text-amber-700",
        tone === "fail" && "bg-rose-50 text-rose-700",
        tone === "neutral" && "bg-ink/5 text-ink/70",
        tone === "brand" && "bg-brand/10 text-brand",
      )}
    >
      {children}
    </span>
  );
}

export function Switch({ checked, onChange, disabled, label }: { checked: boolean; onChange: (v: boolean) => void; disabled?: boolean; label: string }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={clsx("relative h-7 w-12 shrink-0 rounded-full transition disabled:opacity-60", checked ? "bg-brand" : "bg-ink/20")}
    >
      <span className={clsx("absolute top-1 h-5 w-5 rounded-full bg-white shadow transition", checked ? "left-6" : "left-1")} />
    </button>
  );
}

export function Stepper({ value, onChange, min = 1, max = 99, label }: { value: number; onChange: (v: number) => void; min?: number; max?: number; label: string }) {
  return (
    <div className="flex items-center rounded-lg border border-ink/10" aria-label={label}>
      <button type="button" aria-label={`Decrease ${label}`} className="h-8 w-8 text-lg text-ink/60 disabled:opacity-30" disabled={value <= min} onClick={() => onChange(value - 1)}>−</button>
      <span className="w-7 text-center text-sm font-semibold tabular-nums">{value}</span>
      <button type="button" aria-label={`Increase ${label}`} className="h-8 w-8 text-lg text-ink/60 disabled:opacity-30" disabled={value >= max} onClick={() => onChange(value + 1)}>+</button>
    </div>
  );
}

export function ErrorNote({ error }: { error: string | null }) {
  if (!error) return null;
  return <p role="alert" className="rounded-xl bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>;
}

export function Spinner() {
  return <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-r-transparent" />;
}
