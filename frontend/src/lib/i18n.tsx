"use client";
// Lightweight UI translations. The advisor itself answers in any of the
// 10 languages through Gemini; screen labels are translated here.
import { createContext, useContext, useEffect, useState } from "react";

export const LANGS: Record<string, string> = {
  en: "English", hi: "हिन्दी", ta: "தமிழ்", te: "తెలుగు", mr: "मराठी", bn: "বাংলা", gu: "ગુજરાતી", kn: "ಕನ್ನಡ", ml: "മലയാളം", pa: "ਪੰਜਾਬੀ",
};

const en = {
  tagline: "Internet, phones and digital tools for your business. One plan, one bill, in your language.",
  hero: "Get your business online in one sitting",
  start: "Talk to the advisor",
  track: "Track my order",
  partner: "Partner console",
  step_advisor: "Tell us about your business",
  step_quote: "See one monthly price",
  step_kyc: "Verify with photos, no visit",
  step_track: "Track until it's live",
  chat_placeholder: "Type your answer, or tap a chip…",
  send: "Send",
  show_plan: "Show my plan now",
  what_we_know: "What we know so far",
  your_plan: "Your recommended plan",
  per_month: "/month",
  plus_gst: "+ 18% GST",
  setup: "One-time setup",
  contract: "Contract",
  months: "months",
  activation: "Live in about",
  days: "days",
  customise: "Customise & continue",
  addons: "Add-ons you can switch on or off",
  included: "Included",
  held_back: "Not included yet",
  continue_kyc: "Continue to verification",
  continue_short: "Continue",
  total: "Monthly total",
  consent_continue: "I agree, continue",
  gstin_lookup: "Enter your GSTIN for an instant lookup",
  lookup: "Look up",
  upload_docs: "Upload your documents",
  try_sample: "Or load a sample applicant (demo)",
  check_docs: "Check my documents",
  verified: "All documents verified",
  needs_action: "A few things need your attention",
  place_order: "Place order",
  phone: "Mobile number for WhatsApp updates",
  slot: "Preferred installation slot",
  delete_data: "Withdraw consent & delete my data",
  order_code: "Your order code",
  expected: "Expected live by",
  updates: "Updates sent to you",
  simulate: "Simulate next step (demo)",
  enter_code: "Enter your order code",
  why: "Why",
  saving: "Compared with today",
  ai_on: "AI advisor",
  ai_off: "Guided mode",
};

type Dict = typeof en;

const hi: Partial<Dict> = {
  tagline: "आपके बिज़नेस के लिए इंटरनेट, फ़ोन और डिजिटल टूल। एक प्लान, एक बिल, आपकी भाषा में।",
  hero: "एक ही बार में अपना बिज़नेस डिजिटल बनाइए",
  start: "सलाहकार से बात करें",
  track: "ऑर्डर ट्रैक करें",
  partner: "पार्टनर कंसोल",
  step_advisor: "अपने बिज़नेस के बारे में बताइए",
  step_quote: "एक मासिक कीमत देखिए",
  step_kyc: "फ़ोटो से वेरिफ़िकेशन, कोई विज़िट नहीं",
  step_track: "चालू होने तक ट्रैक कीजिए",
  chat_placeholder: "जवाब लिखें या कोई विकल्प चुनें…",
  send: "भेजें",
  show_plan: "अभी प्लान दिखाएँ",
  what_we_know: "अब तक की जानकारी",
  your_plan: "आपके लिए प्लान",
  per_month: "/महीना",
  plus_gst: "+ 18% GST",
  setup: "एक बार का सेटअप",
  contract: "कॉन्ट्रैक्ट",
  months: "महीने",
  activation: "लगभग",
  days: "दिन में चालू",
  customise: "बदलें और आगे बढ़ें",
  addons: "ऐड-ऑन जिन्हें आप चालू/बंद कर सकते हैं",
  included: "शामिल",
  held_back: "अभी शामिल नहीं",
  continue_kyc: "वेरिफ़िकेशन पर आगे बढ़ें",
  continue_short: "आगे बढ़ें",
  total: "मासिक कुल",
  consent_continue: "मैं सहमत हूँ, आगे बढ़ें",
  gstin_lookup: "तुरंत जानकारी के लिए GSTIN लिखें",
  lookup: "खोजें",
  upload_docs: "अपने दस्तावेज़ अपलोड करें",
  try_sample: "या सैंपल आवेदक लोड करें (डेमो)",
  check_docs: "दस्तावेज़ जाँचें",
  verified: "सभी दस्तावेज़ सही हैं",
  needs_action: "कुछ चीज़ें ठीक करनी हैं",
  place_order: "ऑर्डर करें",
  phone: "WhatsApp अपडेट के लिए मोबाइल नंबर",
  slot: "इंस्टॉलेशन का समय",
  delete_data: "सहमति वापस लें और डेटा डिलीट करें",
  order_code: "आपका ऑर्डर कोड",
  expected: "चालू होने की तारीख",
  updates: "आपको भेजे गए अपडेट",
  simulate: "अगला चरण (डेमो)",
  enter_code: "ऑर्डर कोड लिखें",
  why: "क्यों",
  saving: "आज के खर्च से तुलना",
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
  const t = (k: keyof Dict) => (lang === "hi" ? hi[k] ?? en[k] : en[k]);
  return <Ctx.Provider value={{ lang, setLang, t }}>{children}</Ctx.Provider>;
}

export const useI18n = () => useContext(Ctx);
