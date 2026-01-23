"use client";

import { motion } from "framer-motion";
import { LucideIcon, Zap, Shield, Layers } from "lucide-react";

const MoatCard = ({ icon: Icon, title, innovation, moat, delay }: { icon: LucideIcon; title: string; innovation: string; moat: string; delay: number }) => (
    <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        transition={{ delay }}
        className="glass-panel p-8 rounded-2xl border border-white/5 hover:border-purple-500/30 hover:bg-white/[0.02] transition-all group"
    >
        <div className="flex items-start space-x-4">
            <div className="w-14 h-14 bg-purple-500/10 rounded-2xl flex items-center justify-center flex-shrink-0 group-hover:scale-110 transition-transform">
                <Icon className="w-7 h-7 text-purple-glow" />
            </div>
            <div>
                <h3 className="text-xl font-bold text-white mb-2">{title}</h3>
                <p className="text-sm text-gray-400 mb-3">
                    <span className="text-purple-400 font-semibold">Innovation:</span> {innovation}
                </p>
                <p className="text-sm text-gray-500">
                    <span className="text-cyan-400 font-semibold">Moat:</span> {moat}
                </p>
            </div>
        </div>
    </motion.div>
);

export default function TechnicalMoatSection() {
    return (
        <section className="py-24 bg-gradient-to-b from-[var(--background)] to-black relative overflow-hidden">
            <div className="absolute top-[20%] right-[-10%] w-[500px] h-[500px] bg-purple-500/10 blur-[120px] rounded-full pointer-events-none" />

            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="text-center mb-16">
                    <h2 className="text-4xl md:text-6xl font-bold text-white mb-4">
                        Why This Is <br />
                        <span className="text-transparent bg-clip-text bg-gradient-to-r from-purple-400 to-pink-500">
                            Hard To Copy
                        </span>
                    </h2>
                    <p className="text-xl text-gray-400 max-w-2xl mx-auto">
                        Three technical innovations that create durable competitive advantages.
                    </p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <MoatCard
                        icon={Zap}
                        title="Cryptographic Routing (CLR)"
                        innovation="ZK-verified engine that dynamically routes based on Privacy → Value → Sovereignty → Velocity."
                        moat="Complex cross-chain state verification that simple aggregators cannot replicate."
                        delay={0.1}
                    />
                    <MoatCard
                        icon={Layers}
                        title="Dual-Chain Execution"
                        innovation="Polygon CDK for liquidity + Avalanche L1s for sovereign AI custom VMs."
                        moat="Chain-agnostic execution no single-chain protocol can match. Best of both worlds."
                        delay={0.2}
                    />
                    <MoatCard
                        icon={Shield}
                        title="Crash-Proof Agents"
                        innovation="DBOS-integrated workflows that survive node failures."
                        moat="Pause-and-resume execution state. If AWS dies, your agent dies. If VAMS dies, your agent pauses."
                        delay={0.3}
                    />
                </div>
            </div>
        </section>
    );
}
