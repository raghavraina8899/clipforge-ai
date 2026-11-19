import "./globals.css";
import type { Metadata } from "next";
import { Sidebar, MobileNav } from "@/components/sidebar";

export const metadata: Metadata = { title: "ClipForge AI", description: "Free, local AI video clipping for Shorts and Reels" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body>
        <div className="flex min-h-screen">
          <Sidebar />
          <div className="min-w-0 flex-1">
            <MobileNav />
            <main className="mx-auto max-w-7xl p-4 md:p-8">{children}</main>
          </div>
        </div>
      </body>
    </html>
  );
}
