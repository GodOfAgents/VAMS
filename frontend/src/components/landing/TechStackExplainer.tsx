"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Layers, Cpu, Shield, Coins, Box } from "lucide-react";

const LAYERS = [
    {
        id: "l5",
        label: "Layer 5: Economic",
        title: "Incentive & Commerce Layer",
        description: "$VAMS Token, Dynamic TAO emissions, and x402 micropayments. The lifeblood that aligns incentives across the entire machine economy.",
        icon: Coins,
        color: "from-yellow-400 to-orange-500",
        tech: ["$VAMS", "x402 Protocol", "Dynamic TAO"],
    },
    {
        id: "l4",
        label: "Layer 4: Trust",
        title: "Privacy & Verification Layer",
        description: "TEE (Trusted Execution Environments) and ZK Proofs ensure that agent intent is private and execution is verifiable.",
        icon: Shield,
        color: "from-green-400 to-emerald-600",
        tech: ["Phala TEE", "Marlin Oyster", "ZKML"],
    },
    {
        id: "l3",
        label: "Layer 3: Logic",
        title: "State & Orchestration Layer",
        description: "The 'Brain' of VAMS. Distinct execution environments (DBOS) that guarantee 'Immortality'—crashes are impossible, state is persistent.",
        icon: Cpu,
        color: "from-cyan-400 to-blue-600",
        tech: ["DBOS", "Kwil DB", "WeaveDB"],
    },
    {
        id: "l2",
        label: "Layer 2: Compute",
        title: "The Muscle Layer",
        description: "Aggregated physical infrastructure (GPUs/CPUs) sourced from decentralized networks.",
        icon: Box,
        color: "from-purple-400 to-indigo-600",
        tech: ["io.net", "Akash", "Render", "Bittensor"],
    },
    {
        id: "l1",
        label: "Layer 1: Foundational",
        title: "Settlement & DA Layer",
        description: "The Bedrock. Data availability and final settlement guarantees.",
        icon: Layers,
        color: "from-slate-400 to-slate-600",
        tech: ["Celestia DA", "EigenDA", "Polygon CDK"],
    },
];

export default function TechStackExplainer() {
    const [activeLayer, setActiveLayer] = useState(LAYERS[2]); // Default to L3 (Logic)

    return (
        <section className="py-24 bg-[var(--background)] relative">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="text-center mb-16">
                    <h2 className="text-3xl md:text-5xl font-bold text-white mb-4">
                        The 5-Layer Stack
                    </h2>
                    <p className="text-gray-400 max-w-2xl mx-auto">
                        A complete modular architecture designed for the unique needs of autonomous agents.
                    </p>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-16">
                    {/* Left: Layer Selectors */}
                    <div className="lg:col-span-5 flex flex-col space-y-4">
                        {LAYERS.map((layer) => (
                            <button
                                key={layer.id}
                                onClick={() => setActiveLayer(layer)}
                                className={`group relative flex items-center p-4 rounded-xl transition-all duration-300 border text-left
                  ${activeLayer.id === layer.id
                                        ? "bg-white/10 border-white/20 text-white shadow-xl scale-105 z-10"
                                        : "bg-transparent border-transparent text-gray-500 hover:bg-white/5 hover:text-gray-300"
                                    }
                `}
                            >
                                <div
                                    className={`p-2 rounded-lg mr-4 bg-gradient-to-br ${layer.color} opacity-80 group-hover:opacity-100 transition-opacity`}
                                >
                                    <layer.icon className="w-5 h-5 text-white" />
                                </div>
                                <div className="flex-1">
                                    <span className="text-sm font-mono block mb-0.5 opacity-70">{layer.label}</span>
                                    <span className="font-bold">{layer.title}</span>
                                </div>
                                {activeLayer.id === layer.id && (
                                    <motion.div
                                        layoutId="active-indicator"
                                        className="absolute inset-0 border-2 border-cyan-500/30 rounded-xl pointer-events-none"
                                    />
                                )}
                            </button>
                        ))}
                    </div>

                    {/* Right: Content Display */}
                    <div className="lg:col-span-7 relative">
                        <AnimatePresence mode="wait">
                            <motion.div
                                key={activeLayer.id}
                                initial={{ opacity: 0, x: 20 }}
                                animate={{ opacity: 1, x: 0 }}
                                exit={{ opacity: 0, x: -20 }}
                                transition={{ duration: 0.3 }}
                                className="h-full"
                            >
                                <div className="glass-panel p-8 md:p-12 rounded-3xl h-full border border-white/10 relative overflow-hidden">
                                    {/* Ambient Glow */}
                                    <div
                                        className={`absolute top-0 right-0 w-64 h-64 bg-gradient-to-br ${activeLayer.color} opacity-10 blur-[80px] pointer-events-none`}
                                    />

                                    <div className="relative z-10">
                                        <div className={`inline-flex items-center space-x-2 px-3 py-1 rounded-full text-xs font-bold uppercase mb-6 bg-gradient-to-r ${activeLayer.color} text-white`}>
                                            <span>{activeLayer.label}</span>
                                        </div>

                                        <h3 className="text-3xl font-bold text-white mb-6">
                                            {activeLayer.title}
                                        </h3>

                                        <p className="text-lg text-gray-300 leading-relaxed mb-8">
                                            {activeLayer.description}
                                        </p>

                                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                            {activeLayer.tech.map((item) => (
                                                <div key={item} className="flex items-center space-x-3 bg-white/5 px-4 py-3 rounded-lg border border-white/5">
                                                    <div className={`w-2 h-2 rounded-full bg-gradient-to-r ${activeLayer.color}`} />
                                                    <span className="text-gray-300 font-mono text-sm">{item}</span>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                </div>
                            </motion.div>
                        </AnimatePresence>
                    </div>
                </div>
            </div>
        </section>
    );
}
