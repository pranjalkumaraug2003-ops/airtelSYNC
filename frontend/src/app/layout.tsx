import type { Metadata, Viewport } from "next";
import "@fontsource-variable/plus-jakarta-sans";
import "@fontsource/noto-sans-devanagari/400.css";
import "@fontsource/noto-sans-devanagari/600.css";
import "./globals.css";
import { LangProvider } from "@/lib/i18n";


export const metadata: Metadata = {
  title: "Udyam Digital · Accel Business",
  description: "Get your business online in one sitting: advisor, one monthly price, photo KYC and live tracking.",
  manifest: "/manifest.webmanifest",
};

export const viewport: Viewport = { themeColor: "#D7192A", width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="font-sans">
        <LangProvider>{children}</LangProvider>
      </body>
    </html>
  );
}
