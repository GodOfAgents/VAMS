"use client";

import { motion } from "framer-motion";
import { Shield, Zap, Infinity as InfinityIcon, ServerCrash } from "lucide-react";

const features = [
    {
        icon: Zap,
        title: "Crash-Proof Execution",
        desc: "If a node fails, your agent pauses and resumes elsewhere. State is checkpointed on-chain. Execution never restarts—it continues.",
        color: "cyan",
    },
    {
        icon: Shield,
        title: "Censorship Resistant",
        desc: "Code runs in TEEs (Trusted Execution Environments). No single entity can stop your agent or view its private logic.",
        color: "purple",
    },
    {
        icon: InfinityIcon,
        title: "Self-Sustaining",
        desc: "Agents can stake $VAMS to earn rewards. If rewards > compute costs, your agent achieves economic immortality.",
        color: "green",
    },
];

export function Immortality() {
    return (
        <section className="py-24 bg-black relative overflow-hidden">
            {/* Background Chaos vs Order */}
            <div className="absolute inset-0 z-0">
                <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-cyan-900/10 blur-[100px] rounded-full" />
                <div className="absolute bottom-0 left-0 w-[500px] h-[500px] bg-purple-900/10 blur-[100px] rounded-full" />
            </div>

            <div className="container mx-auto px-4 relative z-10 flex flex-col lg:flex-row items-center gap-16">

                {/* Left: Content */}
                <div className="lg:w-1/2 space-y-8">
                    <motion.div
                        initial={{ opacity: 0, x: -20 }}
                        whileInView={{ opacity: 1, x: 0 }}
                        viewport={{ once: true }}
                    >
                        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-green-500/10 border border-green-500/20 text-green-400 text-xs font-mono mb-4">
                            <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
                            STATUS: IMMORTAL
                        </div>
                        <h2 className="text-4xl md:text-6xl font-display font-bold leading-tight">
                            Agents that <br />
                            <span className="text-transparent bg-clip-text bg-gradient-to-r from-green-400 to-cyan-400">Cannot Die.</span>
                        </h2>
                        <p className="text-gray-400 text-lg mt-4 max-w-lg">
                            Traditional bots die when the server crashes. VAMS agents are cryptographically immortal.
                        </p>
                    </motion.div>

                    <div className="space-y-6">
                        {features.map((feature, index) => (
                            <motion.div
                                key={index}
                                initial={{ opacity: 0, x: -20 }}
                                whileInView={{ opacity: 1, x: 0 }}
                                viewport={{ once: true }}
                                transition={{ delay: index * 0.1 }}
                                className="flex items-start gap-4 p-4 rounded-xl hover:bg-white/5 transition-colors border border-transparent hover:border-white/5"
                            >
                                <div className={`p-3 rounded-lg bg-${feature.color}-500/10 text-${feature.color}-400`}>
                                    <feature.icon className="w-6 h-6" />
                                </div>
                                <div>
                                    <h3 className="text-xl font-bold font-display mb-1">{feature.title}</h3>
                                    <p className="text-gray-400 text-sm leading-relaxed">{feature.desc}</p>
                                </div>
                            </motion.div>
                        ))}
                    </div>
                </div>

                {/* Right: Visual Visualization of "Immortality" */}
                <div className="lg:w-1/2 w-full flex justify-center">
                    <div className="relative w-80 h-80 md:w-96 md:h-96">
                        {/* The "Shield" */}
                        <motion.div
                            animate={{ rotate: 360 }}
                            transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
                            className="absolute inset-0 border border-cyan-500/20 rounded-full border-dashed"
                        />
                        <motion.div
                            animate={{ rotate: -360 }}
                            transition={{ duration: 30, repeat: Infinity, ease: "linear" }}
                            className="absolute inset-8 border border-purple-500/20 rounded-full border-dotted"
                        />

                        {/* The "Core" (The Agent) */}
                        <div className="absolute inset-0 flex items-center justify-center">
                            <div className="relative w-32 h-32 bg-gradient-to-br from-cyan-400 to-green-400 rounded-full blur-sm flex items-center justify-center animate-pulse-glow z-20">
                                <div className="w-28 h-28 bg-black rounded-full flex items-center justify-center">
                                    <InfinityIcon className="w-12 h-12 text-cyan-400" />
                                </div>
                            </div>
                        </div>

                        {/* "Attacks" bouncing off */}
                        <AttackParticle delay={0} angle={45} />
                        <AttackParticle delay={2} angle={120} />
                        <AttackParticle delay={1.5} angle={200} />
                        <AttackParticle delay={3.5} angle={300} />

                        {/* Status Indicator */}
                        <div className="absolute -bottom-12 left-1/2 -ml-20 w-40 h-10 bg-black/50 backdrop-blur border border-green-500/30 rounded flex items-center justify-center text-green-400 font-mono text-xs">
                            UPTIME: 100%
                        </div>
                    </div>
                </div>

            </div>
        </section>
    );
}

function AttackParticle({ delay, angle }: { delay: number, angle: number }) {
    return (
        <motion.div
            className="absolute top-1/2 left-1/2 w-4 h-4 text-red-500 z-10"
            initial={{ opacity: 0, x: 0, y: 0 }}
            animate={{
                opacity: [0, 1, 1, 0],
                x: [200 * Math.cos(angle * Math.PI / 180), 60 * Math.cos(angle * Math.PI / 180)],
                y: [200 * Math.sin(angle * Math.PI / 180), 60 * Math.sin(angle * Math.PI / 180)],
                scale: [1, 1.5, 0] // Explode on impact
            }}
            transition={{
                duration: 2,
                repeat: Infinity,
                delay: delay,
                repeatDelay: 2
            }}
        >
            <ServerCrash className="w-full h-full" />
        </motion.div>
    )
}
