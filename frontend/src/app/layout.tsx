import type { Metadata } from "next";
import "../styles/globals.css";
import { Providers } from "@/lib/query-client";
import { Sidebar } from "@/components/layout/sidebar";
import { Header } from "@/components/layout/header";

export const metadata: Metadata = {
  title: "Voice2Flow AI Business Agent",
  description: "Autonomous Business Agent with PostgreSQL Persistence & n8n Orchestration",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="bg-slate-950 text-slate-100 antialiased min-h-screen flex">
        <Providers>
          <Sidebar />
          <div className="flex-1 flex flex-col min-w-0">
            <Header />
            <main className="flex-1 p-8 overflow-y-auto">{children}</main>
          </div>
        </Providers>
      </body>
    </html>
  );
}
