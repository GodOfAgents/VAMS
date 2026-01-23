"use client";

import { motion } from "framer-motion";
import { ArrowRight, Zap } from "lucide-react";

const ComparisonItem = ({ label, traditional, agent, delay }: { label: string; traditional: string; agent: string; delay: number }) => (
    <motion.div
        initial={{ opacity: 0, x: -20 }}
        whileInView={{ opacity: 1, x: 0 }}
        transition={{ delay }}
        className="grid grid-cols-3 gap-4 items-center py-4 border-b border-white/5 last:border-0"
    >
        <div className="text-gray-400 font-medium font-mono text-xs uppercase tracking-tight">{label}</div>
        <div className="text-red-400/80 text-sm font-mono">{traditional}</div>
        <div className="text-cyan-glow font-bold text-sm font-mono">{agent}</div>
    </motion.div>
);

export default function ProblemSolutionSection() {
    return (
        <section className="relative py-32 bg-background overflow-hidden">
            {/* Industrial Grid Background */}
            <div className="absolute inset-0 opacity-5 pointer-events-none">
                <div className="absolute inset-0 bg-[url('/grid.svg')] bg-repeat opacity-20" />
                <div className="absolute inset-0 bg-gradient-to-b from-red-500/10 via-transparent to-transparent" />
            </div>

            <div className="absolute top-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-red-500/50 to-transparent" />

            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                {/* Problem Statement */}
                <div className="text-center mb-16">
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        className="inline-flex items-center space-x-2 bg-red-500/10 border border-red-500/20 rounded-full px-4 py-2 mb-6"
                    >
                        <Zap className="w-4 h-4 text-red-400" />
                        <span className="text-red-400 text-sm font-bold uppercase tracking-wider">The Crisis</span>
                    </motion.div>

                    <h2 className="text-4xl md:text-6xl font-bold text-white mb-6">
                        The Agentic Bottleneck
                    </h2>

                    <div className="flex items-center justify-center space-x-4 mb-8">
                        <div className="text-center">
                            <div className="text-5xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-yellow-400 to-red-500">
                                $50B
                            </div>
                            <div className="text-sm text-gray-500 uppercase tracking-wide">Invested</div>
                        </div>
                        <ArrowRight className="w-8 h-8 text-red-500" />
                        <div className="text-center">
                            <div className="text-5xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-red-500 to-pink-500">
                                &lt;1%
                            </div>
                            <div className="text-sm text-gray-500 uppercase tracking-wide">Utilization</div>
                        </div>
                    </div>

                    <p className="text-xl text-gray-400 max-w-3xl mx-auto">
                        AI Agents are becoming economic actors, but they <span className="text-red-400 font-semibold">cannot effectively use</span> decentralized infrastructure today.
                    </p>
                </div>

                {/* Comparison Table */}
                <div className="max-w-4xl mx-auto">
                    <div className="glass-panel p-8 rounded-2xl border border-white/10">
                        <div className="grid grid-cols-3 gap-4 mb-6 pb-4 border-b border-white/10">
                            <div className="text-gray-500 text-sm font-bold uppercase">Problem</div>
                            <div className="text-gray-500 text-sm font-bold uppercase">Traditional Blockchain</div>
                            <div className="text-cyan-400 text-sm font-bold uppercase">Agent Requirement</div>
                        </div>

                        <ComparisonItem
                            label="Latency"
                            traditional="12+ second blocks"
                            agent="Sub-second feedback"
                            delay={0.1}
                        />
                        <ComparisonItem
                            label="Cost"
                            traditional="10x Gas Swings"
                            agent="Predictable Planning"
                            delay={0.2}
                        />
                        <ComparisonItem
                            label="Context"
                            traditional="Stateless TX"
                            agent="Persistent Memory"
                            delay={0.3}
                        />
                        <ComparisonItem
                            label="Complexity"
                            traditional="10+ Wallets/Tokens"
                            agent="Single API & Currency"
                            delay={0.4}
                        />
                    </div>
                </div>

                {/* The Developer Nightmare */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    className="mt-16 text-center max-w-3xl mx-auto"
                >
                    <div className="bg-red-950/20 border border-red-500/20 rounded-xl p-8">
                        <h3 className="text-2xl font-bold text-white mb-4">The Developer Nightmare</h3>
                        <p className="text-gray-400 mb-6">
                            To build a sovereign agent today, developers must integrate 5+ different protocols:
                        </p>
                        <div className="flex flex-wrap justify-center gap-3 mb-6">
                            {["Celestia", "io.net", "Phala", "Akash", "Hyperlane"].map((protocol, i) => (
                                <span key={i} className="px-4 py-2 bg-white/5 border border-red-500/20 rounded-lg text-sm text-gray-300">
                                    {protocol}
                                </span>
                            ))}
                        </div>
                        <div className="text-red-400 font-bold text-lg">
                            Result: &lt;1% of AI developers build on Web3. They stay on AWS.
                        </div>
                    </div>
                </motion.div>
            </div>
        </section>
    );
}
