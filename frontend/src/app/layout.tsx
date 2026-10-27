import type { Metadata } from "next";
import { IBM_Plex_Sans, Literata } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const literata = Literata({ subsets: ["latin"], variable: "--font-literata" });
const plex = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-plex",
});

export const metadata: Metadata = {
  title: "SocraticAI",
  description: "A tutor that answers with questions and remembers how you learn.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${literata.variable} ${plex.variable}`}>
      <body className="min-h-screen">
        <header className="border-b border-line bg-card">
          <div className="mx-auto max-w-3xl px-4 py-3">
            <Link href="/" className="font-serif text-xl font-semibold text-ink">
              SocraticAI
            </Link>
          </div>
        </header>
        <main className="mx-auto max-w-3xl px-4 py-8">{children}</main>
      </body>
    </html>
  );
}
