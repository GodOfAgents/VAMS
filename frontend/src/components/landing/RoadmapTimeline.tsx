"use client";

import { motion } from "framer-motion";
import { CheckCircle2, Circle, Clock } from "lucide-react";

const MILESTONES = [
    {
        quarter: "Q1 2026",
        title: "Economic Foundation",
        status: "in-progress",
        items: ["Token Contracts", "Staking & Vesting", "Foundry Setup"],
    },
    {
        quarter: "Q1 2026",
        title: "Infrastructure Rails",
        status: "pending",
        items: ["Polygon CDK L3", "AggLayer Integration", "Cross-chain Bridge"],
    },
    {
        quarter: "Q2 2026",
        title: "The Sovereign Web",
        status: "pending",
        items: ["Conditional L1 Router", "Avalanche Elastic L1", "Agent Runtime"],
    },
    {
        quarter: "Q3 2026",
        title: "Guarded Mainnet",
        status: "pending",
        items: ["Security Audits", "Token Generation Event", "Limited Launch"],
    },
    {
        quarter: "Q4 2026",
        title: "Full Decentralization",
        status: "pending",
        items: ["Open Mainnet", "DAO Handover", "Admin Keys Burn"],
    },
];

export default function RoadmapTimeline() {
    return (
        <section className="py-24 bg-[var(--background)] overflow-hidden">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mb-16 text-center">
                <h2 className="text-3xl md:text-5xl font-bold text-white mb-4">
                    Path to Mainnet
                </h2>
                <p className="text-gray-400">
                    A definitive timeline for deploying the VAMS infrastructure.
                </p>
            </div>

            <div className="relative w-full overflow-x-auto pb-12 hide-scrollbar">
                <div className="px-4 sm:px-6 lg:px-8 min-w-[1200px]"> {/* Ensure min width for scrolling */}

                    {/* Timeline Line */}
                    <div className="relative h-1 bg-gray-800 rounded-full mb-12 top-16 -z-10 mx-10">
                        <div className="absolute top-0 left-0 h-full bg-cyan-500 w-[15%]" /> {/* Progress Bar */}
                    </div>

                    <div className="grid grid-cols-5 gap-8">
                        {MILESTONES.map((milestone, index) => (
                            <motion.div
                                key={index}
                                initial={{ opacity: 0, y: 20 }}
                                whileInView={{ opacity: 1, y: 0 }}
                                transition={{ delay: index * 0.1 }}
                                className="relative group"
                            >
                                {/* Node */}
                                <div className="flex justify-center mb-6">
                                    <div className={`w-12 h-12 rounded-full border-4 flex items-center justify-center bg-[var(--background)] z-10 transition-colors duration-300
                    ${milestone.status === 'in-progress' ? 'border-cyan-500 shadow-[0_0_20px_rgba(6,182,212,0.5)]' :
                                            milestone.status === 'completed' ? 'border-green-500 bg-green-900/20' : 'border-gray-700'}
                  `}>
                                        {milestone.status === 'in-progress' && <Clock className="w-5 h-5 text-cyan-500 animate-pulse" />}
                                        {milestone.status === 'completed' && <CheckCircle2 className="w-5 h-5 text-green-500" />}
                                        {milestone.status === 'pending' && <Circle className="w-4 h-4 text-gray-700" />}
                                    </div>
                                </div>

                                {/* Card */}
                                <div className="bg-white/5 border border-white/5 p-6 rounded-xl hover:bg-white/10 transition-colors backdrop-blur-sm">
                                    <span className={`text-xs font-bold uppercase tracking-wider mb-2 block
                    ${milestone.status === 'in-progress' ? 'text-cyan-400' : 'text-gray-500'}
                  `}>
                                        {milestone.quarter}
                                    </span>
                                    <h3 className="text-lg font-bold text-white mb-4">{milestone.title}</h3>
                                    <ul className="space-y-2">
                                        {milestone.items.map((item, i) => (
                                            <li key={i} className="flex items-start space-x-2 text-sm text-gray-400">
                                                <span className="mt-1.5 w-1 h-1 bg-gray-600 rounded-full" />
                                                <span>{item}</span>
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            </motion.div>
                        ))}
                    </div>
                </div>
            </div>
        </section>
    );
}
