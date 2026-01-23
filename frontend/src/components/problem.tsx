"use client";

import { motion } from "framer-motion";
import { XCircle, Clock, DollarSign, Database, Wallet } from "lucide-react";

const frictionPoints = [
    {
        icon: Clock,
        title: "Latency",
        legacy: "12+ Second Blocks",
        needed: "Sub-Second Feedback",
        delay: 0.1,
    },
    {
        icon: DollarSign,
        title: "Cost",
        legacy: "Volatile Gas Swings",
        needed: "Predictable Economics",
        delay: 0.2,
    },
    {
        icon: Database,
        title: "Context",
        legacy: "Stateless Txs",
        needed: "Persistent Memory",
        delay: 0.3,
    },
    {
        icon: Wallet,
        title: "Complexity",
        legacy: "10+ Wallets/Tokens",
        needed: "One API & Token",
        delay: 0.4,
    },
];

export function Problem() {
    return (
        <section className="py-24 bg-black relative overflow-hidden">
            <div className="container mx-auto px-4 relative z-10">
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    className="text-center mb-16"
                >
                    <h2 className="text-4xl md:text-5xl font-display font-bold mb-6">
                        The <span className="text-red-500">Agentic Bottleneck</span>
                    </h2>
                    <p className="text-gray-400 text-xl max-w-2xl mx-auto">
                        AI Agents are becoming economic actors, but traditional blockchain infrastructure is too slow, expensive, and fragmented for them to survive.
                    </p>
                </motion.div>

                <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
                    {frictionPoints.map((item, index) => (
                        <motion.div
                            key={index}
                            initial={{ opacity: 0, y: 20 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true }}
                            transition={{ delay: item.delay }}
                            className="p-6 rounded-xl bg-white/5 border border-white/10 backdrop-blur-sm hover:bg-white/10 transition-colors group"
                        >
                            <div className="w-12 h-12 rounded-full bg-red-500/20 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                                <item.icon className="w-6 h-6 text-red-500" />
                            </div>
                            <h3 className="text-xl font-bold mb-4 font-display">{item.title}</h3>

                            <div className="space-y-3 text-sm">
                                <div className="flex items-center gap-2 text-red-400">
                                    <XCircle className="w-4 h-4" />
                                    <span>{item.legacy}</span>
                                </div>
                                <div className="flex items-center gap-2 text-cyan-400">
                                    <div className="w-4 h-4 rounded-full border border-cyan-400 flex items-center justify-center">
                                        <div className="w-2 h-2 bg-cyan-400 rounded-full" />
                                    </div>
                                    <span>{item.needed}</span>
                                </div>
                            </div>
                        </motion.div>
                    ))}
                </div>
            </div>

            {/* Background Red Glow */}
            <div className="absolute top-1/2 left-1/2 -ml-[500px] -mt-[300px] w-[1000px] h-[600px] bg-red-900/10 blur-[120px] rounded-full pointer-events-none" />
        </section>
    );
}
