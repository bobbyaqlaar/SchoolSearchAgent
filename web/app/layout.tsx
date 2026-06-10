import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Aqlaar Dubai School Finder",
  description: "Search, compare, and explore Dubai private schools by curriculum, area, grade, budget and KHDA rating.",
  icons: {
    icon: [{ url: "/aqlaar-logo.png", type: "image/png" }],
    apple: "/aqlaar-logo.png",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}): React.ReactElement {
  return (
    <html lang="en">
      <body className="flex min-h-screen flex-col">
        <header className="border-b border-border bg-surface dark:border-border-dark dark:bg-surface-dark">
          <nav
            className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3"
            aria-label="Main navigation"
          >
            <Link
              href="/"
              className="rounded text-lg font-semibold text-brand transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
            >
              Aqlaar Dubai School Finder
            </Link>
            <div className="flex items-center gap-3 sm:gap-4">
              <div className="flex gap-1 text-sm sm:gap-2">
                <Link
                  href="/"
                  className="inline-flex items-center rounded px-3 py-1 font-medium text-brand transition-all duration-200 ease-in-out hover:scale-[1.02] hover:bg-brand/10 active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
                >
                  Search
                </Link>
                <Link
                  href="/compare"
                  className="inline-flex items-center rounded px-3 py-1 font-medium text-brand transition-all duration-200 ease-in-out hover:scale-[1.02] hover:bg-brand/10 active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
                >
                  Compare
                </Link>
              </div>
              <Image
                src="/aqlaar-logo.png"
                alt="Aqlaar Tech logo"
                width={44}
                height={44}
                className="h-9 w-9 shrink-0 object-contain sm:h-10 sm:w-10"
                priority
              />
            </div>
          </nav>
        </header>
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">{children}</main>
        <footer className="border-t border-border bg-surface dark:border-border-dark dark:bg-surface-dark">
          <p className="mx-auto max-w-6xl px-4 py-4 text-center text-xs text-muted dark:text-muted-dark">
            Copyright © 2026 Aqlaar Tech FZE LLC. All rights reserved.
          </p>
        </footer>
      </body>
    </html>
  );
}
