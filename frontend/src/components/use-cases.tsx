"use client";

import { motion } from "framer-motion";
import { TrendingUp, Gamepad2, Users, Radio, ArrowUpRight } from "lucide-react";

const useCases = [
    {
        icon: TrendingUp,
        title: "DeFAI & Trading",
        market: "$150B+ TVL",
        desc: "Sub-second cross-chain settlement for high-frequency trading agents. MEV protection via TEEs.",
        color: "green",
    },
    {
        icon: Gamepad2,
        title: "Cloud Gaming",
        market: "$65B Market",
        desc: "Dedicated Avalanche L1s for lag-free multiplayer. Decentralized GPU rendering via Render Network.",
        color: "purple",
    },
    {
        icon: Users,
        title: "DAO Infrastructure",
        market: "$25B AUM",
        desc: "Automated treasury management and proposal execution using DBOS durable workflows.",
        color: "blue",
    },
    {
        icon: Radio,
        title: "IoT & DePIN",
        market: "$1.1T Economy",
        desc: "High-frequency sensor data on Near DA. Edge compute via Akash for autonomous device networks.",
        color: "cyan",
    },
];

export function UseCases() {
    return (
        <section className="py-24 bg-deep-space relative overflow-hidden">
            <div className="container mx-auto px-4 relative z-10">
                <div className="flex flex-col md:flex-row items-end justify-between mb-16 gap-6">
                    <motion.div
                        initial={{ opacity: 0, x: -20 }}
                        whileInView={{ opacity: 1, x: 0 }}
                        viewport={{ once: true }}
                    >
                        <div className="text-cyan-400 text-sm font-mono mb-2">TARGET MARKETS</div>
                        <h2 className="text-4xl md:text-5xl font-display font-bold">
                            Powering the <br />
                            <span className="text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-green-400">Agentic Economy</span>
                        </h2>
                    </motion.div>

                    <motion.div
                        initial={{ opacity: 0, x: 20 }}
                        whileInView={{ opacity: 1, x: 0 }}
                        viewport={{ once: true }}
                        className="max-w-md text-gray-400 text-right md:text-left"
                    >
                        From high-frequency trading to autonomous worlds, VAMS provides the sovereign infrastructure for next-gen workloads.
                    </motion.div>
                </div>

                <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
                    {useCases.map((item, index) => (
                        <motion.div
                            key={index}
                            initial={{ opacity: 0, y: 20 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true }}
                            transition={{ delay: index * 0.1 }}
                            className="group relative p-6 rounded-2xl bg-white/5 border border-white/10 hover:bg-white/10 transition-colors"
                        >
                            <div className="absolute top-6 right-6 opacity-0 group-hover:opacity-100 transition-opacity">
                                <ArrowUpRight className="w-5 h-5 text-gray-400" />
                            </div>

                            <div className={`w-12 h-12 rounded-lg bg-${item.color}-500/10 flex items-center justify-center mb-6`}>
                                <item.icon className={`w-6 h-6 text-${item.color}-400`} />
                            </div>

                            <div className="mb-2">
                                <span className={`text-xs font-mono px-2 py-1 rounded-full bg-${item.color}-500/10 text-${item.color}-400 border border-${item.color}-500/20`}>
                                    {item.market}
                                </span>
                            </div>

                            <h3 className="text-xl font-bold font-display mb-3 text-white">{item.title}</h3>
                            <p className="text-sm text-gray-400 leading-relaxed text-balance">
                                {item.desc}
                            </p>
                        </motion.div>
                    ))}
                </div>
            </div>
        </section>
    );
}
