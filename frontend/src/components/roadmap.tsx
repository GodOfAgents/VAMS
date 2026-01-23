"use client";

import { motion } from "framer-motion";
import { CheckCircle2, Circle, Rocket } from "lucide-react";

const phases = [
    {
        phase: "Phase 1: Foundation",
        time: "Weeks 1-8",
        title: "Economic Core",
        items: ["$VAMS Token & Staking Contracts", "Deploy to Sepolia & Avalanche Fuji", "Fee Collector Logic"],
        status: "in-progress",
    },
    {
        phase: "Phase 2: Integration",
        time: "Weeks 9-12",
        title: "Avalanche & Teleporter",
        items: ["Deploy Contracts to Avalanche C-Chain", "Integrate Teleporter Bridge", "Gateway MVP"],
        status: "upcoming",
    },
    {
        phase: "Phase 3: The Engine",
        time: "Weeks 13-16",
        title: "CLR & Sovereign L1",
        items: ["Launch Conditional L1 Router (CLR)", "Spin up VAMS Sovereign L1 (ACP-77)", "AWM Integration"],
        status: "upcoming",
    },
    {
        phase: "Phase 4: Launch",
        time: "Weeks 17-24",
        title: "Dashboard & Testnet",
        items: ["AWS-Style Developer Console", "DePIN Integrations (Akash/Arweave)", "Public Testnet Launch"],
        status: "upcoming",
    },
];

export function Roadmap() {
    return (
        <section className="py-24 bg-background relative overflow-hidden">
            <div className="container mx-auto px-4 relative z-10">
                <div className="text-center mb-16">
                    <div className="inline-block px-4 py-1.5 rounded-full border border-green-500/30 bg-green-500/10 text-green-400 text-sm font-mono mb-6 animate-pulse">
                        EXECUTION PLAN
                    </div>
                    <h2 className="text-4xl md:text-5xl font-display font-bold">
                        Roadmap to <span className="text-cyan-400">Mainnet</span>
                    </h2>
                </div>

                <div className="max-w-4xl mx-auto">
                    {phases.map((phase, index) => (
                        <motion.div
                            key={index}
                            initial={{ opacity: 0, x: -50 }}
                            whileInView={{ opacity: 1, x: 0 }}
                            viewport={{ once: true }}
                            transition={{ delay: index * 0.2 }}
                            className="relative pl-12 pb-12 border-l border-white/10 last:pb-0"
                        >
                            {/* Timeline Dot */}
                            <div className={`absolute left-[-9px] top-0 w-4 h-4 rounded-full border-2 ${phase.status === 'in-progress' ? 'bg-cyan-500 border-cyan-500 shadow-[0_0_10px_rgba(6,182,212,0.5)]' : 'bg-black border-gray-600'}`} />

                            <div className="flex flex-col md:flex-row md:items-center justify-between mb-4">
                                <div>
                                    <span className={`text-sm font-mono ${phase.status === 'in-progress' ? 'text-cyan-400' : 'text-gray-500'}`}>
                                        {phase.phase} • {phase.time}
                                    </span>
                                    <h3 className="text-2xl font-bold font-display mt-1">{phase.title}</h3>
                                </div>
                                {phase.status === 'in-progress' && (
                                    <div className="flex items-center gap-2 text-cyan-400 text-sm font-bold mt-2 md:mt-0 px-3 py-1 bg-cyan-900/20 rounded-full border border-cyan-500/30">
                                        <Rocket className="w-4 h-4" />
                                        CURRENT FOCUS
                                    </div>
                                )}
                            </div>

                            <div className="grid md:grid-cols-2 gap-3">
                                {phase.items.map((item, i) => (
                                    <div key={i} className="flex items-center gap-3 p-3 rounded-lg bg-white/5 border border-white/5">
                                        {phase.status === 'completed' ? (
                                            <CheckCircle2 className="w-5 h-5 text-green-500" />
                                        ) : (
                                            <Circle className="w-3 h-3 text-gray-600" />
                                        )}
                                        <span className="text-gray-300 text-sm">{item}</span>
                                    </div>
                                ))}
                            </div>
                        </motion.div>
                    ))}
                </div>
            </div>
        </section>
    );
}
