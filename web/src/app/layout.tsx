import type { Metadata } from "next";
import "./globals.css";
import { Navbar } from "@/components/Navbar";
import { AuthProvider } from "@/contexts/AuthContext";

export const metadata: Metadata = {
  title: "ClipFarm — Volleyball Highlights",
  description: "Automatically clip and organize volleyball highlights from game footage.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="min-h-screen bg-background text-foreground antialiased">
        <AuthProvider>
          <Navbar />
          <main className="mx-auto max-w-6xl px-5 py-10">{children}</main>
        </AuthProvider>
      </body>
    </html>
  );
}
