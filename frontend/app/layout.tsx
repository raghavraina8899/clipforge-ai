import "./globals.css";
import type { Metadata } from "next";
import { Sidebar, MobileNav } from "@/components/sidebar";

import { BRAND } from "@/lib/brand";

export const metadata: Metadata = { title: `${BRAND.name} · AI video clipper`, description: BRAND.tagline };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body>
        <div className="flex min-h-screen">
          <Sidebar />
          <div className="min-w-0 flex-1">
            <MobileNav />
            <main className="mx-auto max-w-7xl animate-fade-up p-4 md:p-8">{children}</main>
          </div>
        </div>
      </body>
    </html>
  );
}
