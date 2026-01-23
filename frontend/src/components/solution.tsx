"use client";

import { motion } from "framer-motion";
import { Cpu, CreditCard, ShieldCheck } from "lucide-react";

const pillars = [
    {
        icon: Cpu,
        title: "Unified Access",
        desc: "One API to access Compute (io.net), Storage (Arweave), and Logic (Kwil). Stop integrating 10 different SDKs.",
        gradient: "from-cyan-400 to-blue-500",
    },
    {
        icon: CreditCard,
        title: "Economic Abstraction",
        desc: "One token ($VAMS) pays for everything. We auto-swap to ETH, SOL, AKT, or IO on the backend.",
        gradient: "from-purple-400 to-pink-500",
    },
    {
        icon: ShieldCheck,
        title: "Agent-Native",
        desc: "Built for software, not humans. Crash-proof execution, micropayments, and verifiable state.",
        gradient: "from-emerald-400 to-teal-500",
    },
];

export function Solution() {
    return (
        <section className="py-24 bg-background relative overflow-hidden">
            <div className="container mx-auto px-4 relative z-10">
                <div className="text-center mb-16">
                    <motion.div
                        initial={{ opacity: 0, scale: 0.9 }}
                        whileInView={{ opacity: 1, scale: 1 }}
                        viewport={{ once: true }}
                        className="inline-block px-4 py-1.5 rounded-full border border-cyan-500/30 bg-cyan-500/10 text-cyan-400 text-sm font-mono mb-6"
                    >
                        THE SOLUTION
                    </motion.div>

                    <h2 className="text-4xl md:text-5xl font-display font-bold mb-6">
                        VAMS: The <span className="text-transparent bg-clip-text bg-gradient-to-r from-cyan-glow to-purple-glow">Sovereign Brain</span>
                    </h2>
                    <p className="text-gray-400 text-xl max-w-2xl mx-auto">
                        A unified Layer 3 Meta-Architecture that acts as the operating system for decentralized agents.
                    </p>
                </div>

                <div className="grid lg:grid-cols-3 gap-8">
                    {pillars.map((pillar, index) => (
                        <motion.div
                            key={index}
                            initial={{ opacity: 0, y: 30 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true }}
                            transition={{ delay: index * 0.2 }}
                            className="relative p-8 rounded-2xl bg-white/5 border border-white/10 overflow-hidden group hover:border-white/20 transition-colors"
                        >
                            {/* Hover Gradient Background */}
                            <div className={`absolute inset-0 bg-gradient-to-br ${pillar.gradient} opacity-0 group-hover:opacity-10 transition-opacity duration-500`} />

                            <div className={`w-14 h-14 rounded-xl bg-gradient-to-br ${pillar.gradient} p-0.5 mb-6`}>
                                <div className="w-full h-full bg-black rounded-[10px] flex items-center justify-center">
                                    <pillar.icon className="w-7 h-7 text-white" />
                                </div>
                            </div>

                            <h3 className="text-2xl font-bold mb-4 font-display">{pillar.title}</h3>
                            <p className="text-gray-400 leading-relaxed group-hover:text-gray-300 transition-colors">
                                {pillar.desc}
                            </p>
                        </motion.div>
                    ))}
                </div>
            </div>
        </section>
    );
}
