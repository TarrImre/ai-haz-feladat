import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Toaster } from "sonner";
import { publicSans } from "@/lib/fonts";
import "./globals.css";

export const metadata: Metadata = {
  title: "Számlafeldolgozó",
  description: "Forintos cash-flow kimutatás PDF-számlákból, MNB-árfolyammal",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="hu" className={publicSans.className}>
      <body>
        {children}
        <Toaster position="top-center" richColors />
      </body>
    </html>
  );
}
