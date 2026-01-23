import type { Metadata } from "next";
import { Inter, Orbitron } from "next/font/google";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const orbitron = Orbitron({
  variable: "--font-orbitron",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "VAMS | The Sovereign Brain",
  description: "The AWS of Web3 for Autonomous AI Agents. Any Agent. Any Chain. One Stack.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${inter.variable} ${orbitron.variable} antialiased bg-background text-foreground font-sans selection:bg-cyan-500/30 selection:text-cyan-100`}
      >
        {children}
      </body>
    </html>
  );
}
