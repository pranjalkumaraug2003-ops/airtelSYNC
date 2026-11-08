"use client";
// Lightweight UI translations. The advisor itself answers in any of the
// 10 languages through Gemini; screen labels are translated here.
import { createContext, useContext, useEffect, useState } from "react";
import { DICTS, en, type Dict } from "./translations";

export const LANGS: Record<string, string> = {
  en: "English", hi: "हिन्दी", ta: "தமிழ்", te: "తెలుగు", mr: "मराठी", bn: "বাংলা", gu: "ગુજરાતી", kn: "ಕನ್ನಡ", ml: "മലയാളം", pa: "ਪੰਜਾਬੀ",
};

const Ctx = createContext<{ lang: string; setLang: (l: string) => void; t: (k: keyof Dict) => string }>({
  lang: "en",
  setLang: () => {},
  t: (k) => en[k],
});

export function LangProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState("en");
  useEffect(() => {
    try {
      const saved = localStorage.getItem("ud_lang");
      if (saved && LANGS[saved]) setLangState(saved);
    } catch {}
  }, []);
  const setLang = (l: string) => {
    setLangState(l);
    try {
      localStorage.setItem("ud_lang", l);
    } catch {}
  };
  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);
  const t = (k: keyof Dict) => DICTS[lang]?.[k] ?? en[k];
  return <Ctx.Provider value={{ lang, setLang, t }}>{children}</Ctx.Provider>;
}

export const useI18n = () => useContext(Ctx);
