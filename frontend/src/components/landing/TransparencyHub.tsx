"use client";

import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { LucideIcon, Shield, CheckCircle2, Terminal, Code, Cpu, Database } from "lucide-react";

interface AuditEntry {
    id: string;
    type: "COMMIT" | "VERIFY" | "SPEC";
    content: string;
    hash: string;
    timestamp: string;
}

const INITIAL_AUDITS: AuditEntry[] = [
    { id: "1", type: "SPEC", content: "ARCHITECTURE_v0-3-0.md Updated", hash: "5f4dcc3b5aa7...", timestamp: "2m ago" },
    { id: "2", type: "COMMIT", content: "Implement CLR Routing Layer", hash: "8f304f1b9b3b...", timestamp: "10m ago" },
    { id: "3", type: "VERIFY", content: "Dual-Chain Consistency Check", hash: "PASS", timestamp: "Active" },
];

export default function TransparencyHub() {
    const [audits] = useState<AuditEntry[]>(INITIAL_AUDITS);

    return (
        <section className="relative py-24 bg-black border-y border-white/5 overflow-hidden">
            {/* Background Matrix/Grid Effect */}
            <div className="absolute inset-0 opacity-[0.03] pointer-events-none">
                <div className="grid grid-cols-12 h-full">
                    {Array.from({ length: 12 }).map((_, i) => (
                        <div key={i} className="border-r border-cyan-500/50 h-full" />
                    ))}
                </div>
            </div>

            <div className="container mx-auto px-6 relative z-10">
                <div className="flex flex-col lg:flex-row gap-16">
                    {/* Left: Interactive Audit Trail */}
                    <div className="lg:w-2/3 space-y-8">
                        <div className="space-y-4">
                            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-cyan-500/10 border border-cyan-500/20">
                                <Shield className="w-3 h-3 text-cyan-glow" />
                                <span className="text-[10px] text-cyan-glow font-mono uppercase tracking-widest">Live Audit Trail</span>
                            </div>
                            <h2 className="text-4xl md:text-5xl font-display font-bold">
                                The Ledger of <br />
                                <span className="text-gradient">Radical Sovereignty</span>
                            </h2>
                            <p className="text-gray-400 max-w-xl text-lg">
                                VAMS is not just a protocol; it&apos;s a verifiable truth machine. Every logic update, every fee adjustment, and every technical spec is cryptographically anchored.
                            </p>
                        </div>

                        <div className="glass-panel rounded-2xl border border-white/10 overflow-hidden">
                            <div className="p-4 bg-white/5 border-b border-white/10 flex justify-between items-center">
                                <div className="flex items-center gap-2">
                                    <Terminal className="w-4 h-4 text-gray-500" />
                                    <span className="text-xs font-mono text-gray-500 uppercase">Live Verification Stream</span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                                    <span className="text-[10px] font-mono text-green-500 uppercase">Synced</span>
                                </div>
                            </div>

                            <div className="divide-y divide-white/5">
                                <AnimatePresence>
                                    {audits.map((audit) => (
                                        <motion.div
                                            key={audit.id}
                                            initial={{ opacity: 0, x: -20 }}
                                            animate={{ opacity: 1, x: 0 }}
                                            className="p-6 flex items-start justify-between group hover:bg-white/[0.02] transition-colors"
                                        >
                                            <div className="flex items-start gap-4">
                                                <div className="mt-1">
                                                    {audit.type === "SPEC" && <Database className="w-5 h-5 text-purple-glow" />}
                                                    {audit.type === "COMMIT" && <Code className="w-5 h-5 text-cyan-glow" />}
                                                    {audit.type === "VERIFY" && <Shield className="w-5 h-5 text-green-500" />}
                                                </div>
                                                <div>
                                                    <p className="text-sm font-bold text-white group-hover:text-cyan-glow transition-colors">
                                                        {audit.content}
                                                    </p>
                                                    <p className="text-xs font-mono text-gray-500 mt-1 uppercase tracking-tighter">
                                                        Origin: {audit.hash}
                                                    </p>
                                                </div>
                                            </div>
                                            <span className="text-[10px] font-mono text-gray-600 uppercase pt-1">
                                                {audit.timestamp}
                                            </span>
                                        </motion.div>
                                    ))}
                                </AnimatePresence>
                            </div>

                            <div className="p-4 bg-black/40 text-center">
                                <button className="text-xs font-mono text-gray-500 hover:text-white transition-colors uppercase tracking-widest flex items-center gap-2 mx-auto">
                                    View Full Provenance <CheckCircle2 className="w-3 h-3" />
                                </button>
                            </div>
                        </div>
                    </div>

                    {/* Right: Technical Badges / Stats */}
                    <div className="lg:w-1/3 grid grid-cols-1 gap-6">
                        <BadgeCard
                            icon={Cpu}
                            title="Verifiable TEE"
                            desc="Hardware-level proof that agent logic is executing exactly as specified."
                            status="Active"
                        />
                        <BadgeCard
                            icon={Shield}
                            title="Proof of Logic"
                            desc="Each agent state transition is signed and verifiable by any node."
                            status="Verified"
                        />
                        <div className="glass-panel p-8 rounded-2xl border border-cyan-500/20 bg-cyan-500/5 flex flex-col items-center text-center space-y-4">
                            <div className="text-cyan-glow">
                                <CheckCircle2 className="w-12 h-12" />
                            </div>
                            <h3 className="font-display font-bold text-xl uppercase tracking-wider">System Integrity</h3>
                            <p className="text-sm text-gray-400">VAMS Gateway currently maintaining 99.99% cryptographic uptime.</p>
                            <div className="w-full h-1 bg-white/5 rounded-full overflow-hidden">
                                <motion.div
                                    initial={{ width: 0 }}
                                    whileInView={{ width: "99.99%" }}
                                    className="h-full bg-cyan-glow"
                                />
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </section>
    );
}

function BadgeCard({ icon: Icon, title, desc, status }: { icon: LucideIcon; title: string; desc: string; status: string }) {
    return (
        <div className="glass-panel p-6 rounded-2xl border border-white/5 hover:border-white/10 transition-colors">
            <div className="flex items-start gap-4">
                <div className="p-3 bg-white/5 rounded-xl">
                    <Icon className="w-6 h-6 text-gray-400" />
                </div>
                <div>
                    <div className="flex items-center gap-2">
                        <h4 className="text-sm font-bold text-white uppercase tracking-wider">{title}</h4>
                        <span className="text-[8px] font-mono text-green-500 border border-green-500/30 px-1.5 py-0.5 rounded uppercase">
                            {status}
                        </span>
                    </div>
                    <p className="text-xs text-gray-500 mt-2 leading-relaxed">
                        {desc}
                    </p>
                </div>
            </div>
        </div>
    );
}
