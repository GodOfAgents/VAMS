"use client";

import { motion } from "framer-motion";
import { LucideIcon, Check, Cpu, Coins, Shield, ArrowRight } from "lucide-react";

const PillarCard = ({ icon: Icon, title, description, delay }: { icon: LucideIcon; title: string; description: string; delay: number }) => (
    <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        transition={{ delay }}
        className="glass-panel p-8 rounded-2xl border border-white/10 hover:border-cyan-500/30 transition-all group"
    >
        <div className="w-16 h-16 bg-gradient-to-br from-cyan-500/20 to-purple-500/20 rounded-xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
            <Icon className="w-8 h-8 text-cyan-400" />
        </div>
        <h3 className="text-2xl font-bold text-white mb-4">{title}</h3>
        <p className="text-gray-400 leading-relaxed">{description}</p>
    </motion.div>
);

export default function WhyVAMSWinsSection() {
    return (
        <section className="py-24 bg-[var(--background)] relative">
            {/* Decorative Elements */}
            <div className="absolute top-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-cyan-500/30 to-transparent" />
            <div className="absolute top-[30%] left-[-10%] w-[400px] h-[400px] bg-cyan-500/10 blur-[100px] rounded-full pointer-events-none" />

            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                {/* Header */}
                <div className="text-center mb-16">
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        className="inline-flex items-center space-x-2 bg-cyan-500/10 border border-cyan-500/20 rounded-full px-4 py-2 mb-6"
                    >
                        <Check className="w-4 h-4 text-cyan-400" />
                        <span className="text-cyan-400 text-sm font-bold uppercase tracking-wider">The Solution</span>
                    </motion.div>

                    <h2 className="text-4xl md:text-6xl font-bold text-white mb-6">
                        Why VAMS Wins
                    </h2>

                    <p className="text-xl text-gray-400 max-w-3xl mx-auto">
                        A <span className="text-white font-semibold">Layer 3 Meta-Architecture</span> that acts as the operating system for decentralized agents.
                    </p>
                </div>

                {/* Three Pillars */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-20">
                    <PillarCard
                        icon={Cpu}
                        title="Unified Access"
                        description="One API to access Compute, Storage, and Logic across all DePIN providers. No more SDK hell."
                        delay={0.1}
                    />
                    <PillarCard
                        icon={Coins}
                        title="Economic Abstraction"
                        description="Pay with $VAMS for everything. Protocol handles conversion to AKT, IO, TAO automatically."
                        delay={0.2}
                    />
                    <PillarCard
                        icon={Shield}
                        title="Agent-Native"
                        description="Built for software, not humans. Micropayments via x402, crash-proof state with DBOS."
                        delay={0.3}
                    />
                </div>

                {/* CLR Diagram */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    className="max-w-5xl mx-auto"
                >
                    <div className="text-center mb-8">
                        <h3 className="text-3xl font-bold text-white mb-3">
                            The Magic: <span className="text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-purple-400">Conditional L1 Router</span>
                        </h3>
                        <p className="text-gray-400">
                            Our proprietary engine automates the hardest part of Web3: <span className="text-white font-semibold">Chain Selection</span>.
                        </p>
                    </div>

                    <div className="glass-panel p-8 md:p-12 rounded-2xl border border-cyan-500/20 bg-gradient-to-br from-cyan-950/10 to-purple-950/10">
                        {/* CLR Flow */}
                        <div className="space-y-4">
                            {/* Input */}
                            <div className="flex items-center justify-center">
                                <div className="px-6 py-3 bg-white/10 rounded-lg border border-white/20 text-white font-mono text-sm">
                                    Agent Request
                                </div>
                            </div>

                            <div className="flex justify-center">
                                <ArrowRight className="w-6 h-6 text-cyan-400 rotate-90" />
                            </div>

                            {/* CLR */}
                            <div className="flex items-center justify-center">
                                <div className="px-8 py-4 bg-gradient-to-r from-cyan-500/20 to-purple-500/20 rounded-lg border border-cyan-500/50 text-white font-bold text-center">
                                    VAMS CLR
                                </div>
                            </div>

                            <div className="flex justify-center">
                                <ArrowRight className="w-6 h-6 text-cyan-400 rotate-90" />
                            </div>

                            {/* Routing Options */}
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-6">
                                <RouteOption condition="Value > $10k" destination="Ethereum" color="from-blue-500/20 to-indigo-500/20" />
                                <RouteOption condition="Privacy?" destination="Phala TEE" color="from-green-500/20 to-emerald-500/20" />
                                <RouteOption condition="Sovereignty?" destination="Avalanche L1" color="from-purple-500/20 to-pink-500/20" />
                                <RouteOption condition="Velocity < 500ms?" destination="Solana/SEI" color="from-orange-500/20 to-yellow-500/20" />
                            </div>

                            {/* Default */}
                            <div className="mt-6 flex items-center justify-center">
                                <div className="px-6 py-3 bg-gradient-to-r from-cyan-500/30 to-purple-500/30 rounded-lg border border-cyan-500/50 text-center">
                                    <div className="text-xs text-gray-400 mb-1">DEFAULT</div>
                                    <div className="text-white font-bold">Polygon CDK (Primary L3)</div>
                                </div>
                            </div>
                        </div>

                        <div className="mt-8 text-center text-sm text-gray-500 font-mono">
                            Zero developer effort. 100% Optimization.
                        </div>
                    </div>
                </motion.div>
            </div>
        </section>
    );
}

function RouteOption({ condition, destination, color }: { condition: string; destination: string; color: string }) {
    return (
        <div className={`p-4 bg-gradient-to-br ${color} rounded-lg border border-white/10`}>
            <div className="text-xs text-gray-400 mb-1">{condition}</div>
            <div className="text-white font-bold text-sm flex items-center">
                <ArrowRight className="w-4 h-4 mr-2" />
                {destination}
            </div>
        </div>
    );
}
