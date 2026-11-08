"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button, Card, Shell } from "@/components/ui";
import { useI18n } from "@/lib/i18n";

export default function TrackEntry() {
  const { t } = useI18n();
  const router = useRouter();
  const [code, setCode] = useState("");
  return (
    <Shell step={3}>
      <Card>
        <h1 className="text-base font-bold">{t("enter_code")}</h1>
        <p className="text-xs text-ink/50">It's in your WhatsApp/SMS confirmation, e.g. UD-7K3P2Q.</p>
        <form className="mt-3 flex gap-2" onSubmit={(e) => { e.preventDefault(); if (code) router.push(`/track/${code.trim().toUpperCase()}`); }}>
          <input value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} aria-label="Order code" placeholder="UD-XXXXXX"
            className="min-h-[44px] flex-1 rounded-xl border border-ink/10 px-3 font-mono text-sm outline-none focus:border-brand" />
          <Button type="submit">{t("track")}</Button>
        </form>
      </Card>
    </Shell>
  );
}
