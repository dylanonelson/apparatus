import type { Metadata } from "next";

import { ThStoreProvider } from "@/lib/ThStoreProvider";
import { ThPreferencesProvider } from "@/preferences/ThPreferencesProvider";
import { ThI18nProvider } from "@/i18n/ThI18nProvider";

import "./app.css";

export const runtime = "edge";

export const metadata: Metadata = {
  title: "Apparatus Ebooks",
  description: "An open-source ebook/audiobook/comics Web Reader",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <ThStoreProvider>
          <ThPreferencesProvider>
            <ThI18nProvider>{children}</ThI18nProvider>
          </ThPreferencesProvider>
        </ThStoreProvider>
      </body>
    </html>
  );
}
