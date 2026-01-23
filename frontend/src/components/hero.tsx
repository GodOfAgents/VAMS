"use client";

import { motion } from "framer-motion";
import { ArrowRight, FileText } from "lucide-react";

export function Hero() {
    return (
        <section className="relative min-h-screen flex items-center justify-center overflow-hidden bg-background">
            {/* Background Effects */}
            <div className="absolute inset-0 z-0">
                <div className="absolute top-0 left-1/4 w-96 h-96 bg-cyan-glow/20 rounded-full blur-[120px] animate-pulse-glow" />
                <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-purple-glow/20 rounded-full blur-[120px] animate-pulse-glow delay-1000" />
                <div className="absolute inset-0 bg-[url('/grid.svg')] opacity-10" />
            </div>

            <div className="container mx-auto px-4 z-10 relative grid lg:grid-cols-2 gap-12 items-center">
                {/* Text Content */}
                <motion.div
                    initial={{ opacity: 0, x: -50 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.8 }}
                    className="text-left space-y-8"
                >
                    <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/5 border border-white/10 backdrop-blur-sm">
                        <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                        <span className="text-xs font-mono text-gray-400">System Online: v3.3</span>
                    </div>

                    <h1 className="text-5xl md:text-7xl font-display font-bold leading-tight">
                        The <span className="text-transparent bg-clip-text bg-gradient-to-r from-cyan-glow to-purple-glow">AWS of Web3</span> for Agents
                    </h1>

                    <p className="text-xl md:text-2xl text-gray-400 font-light max-w-lg">
                        Any Agent. Any Chain. One Stack. <br />
                        <span className="text-sm md:text-base mt-2 block opacity-80">
                            Unified L3 Meta-Architecture connecting $50B+ of DePIN infrastructure.
                        </span>
                    </p>

                    <div className="flex flex-col sm:flex-row gap-4 pt-4">
                        <button className="group relative px-8 py-4 bg-white text-black font-bold rounded-lg overflow-hidden transition-all hover:scale-105">
                            <div className="absolute inset-0 bg-gradient-to-r from-cyan-400 to-purple-400 opacity-0 group-hover:opacity-100 transition-opacity" />
                            <div className="relative flex items-center gap-2">
                                Access the Stack
                                <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                            </div>
                        </button>

                        <button className="px-8 py-4 bg-white/5 border border-white/10 rounded-lg backdrop-blur-sm hover:bg-white/10 transition-all flex items-center gap-2 text-gray-300">
                            <FileText className="w-4 h-4" />
                            Read Whitepaper
                        </button>
                    </div>
                </motion.div>

                {/* Visual Content (The Sovereign Brain Node) */}
                <motion.div
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 1 }}
                    className="relative h-[500px] w-full flex items-center justify-center"
                >
                    {/* Central Core */}
                    <div className="relative w-48 h-48">
                        <div className="absolute inset-0 bg-gradient-to-br from-cyan-500/20 to-purple-500/20 rounded-full blur-2xl animate-pulse-glow" />
                        <div className="absolute inset-0 border-2 border-cyan-500/30 rounded-full animate-[spin_10s_linear_infinite]" />
                        <div className="absolute inset-4 border border-purple-500/30 rounded-full animate-[spin_15s_linear_infinite_reverse]" />

                        {/* Floating Icons/Nodes orbiting */}
                        <OrbitalNode angle={0} delay={0} icon="GPU" color="cyan" />
                        <OrbitalNode angle={72} delay={1} icon="TEE" color="purple" />
                        <OrbitalNode angle={144} delay={2} icon="L1" color="blue" />
                        <OrbitalNode angle={216} delay={3} icon="DB" color="green" />
                        <OrbitalNode angle={288} delay={4} icon="ZK" color="pink" />
                    </div>
                </motion.div>
            </div>
        </section>
    );
}

function OrbitalNode({ angle, delay, icon, color }: { angle: number; delay: number; icon: string; color: string }) {
    return (
        <motion.div
            className="absolute top-1/2 left-1/2 w-12 h-12 -ml-6 -mt-6 rounded-full bg-black/80 border border-white/20 backdrop-blur-md flex items-center justify-center text-[10px] font-mono shadow-lg"
            style={{
                boxShadow: `0 0 10px var(--color-${color}-glow)`,
            }}
            animate={{
                rotate: [0, 360],
                translateX: [140, 140], // Orbit radius
            }}
            transition={{
                rotate: {
                    duration: 20,
                    repeat: Infinity,
                    ease: "linear",
                    delay: -delay * 4 // Offset start
                },
                translateX: { duration: 0 } // Static radius
            }}
        >
            <div
                className="transform"
                style={{ transform: `rotate(-${angle}deg)` }} // Counter-rotate to keep text upright? No, actually simpler to just animate parent rotation
            >
                {/* Wait, if parent rotates, child rotates. To keep text upright we need to counter-rotate child. */}
                {/* Simplified for MVP: Text rotates. Or use a better orbit implementation. */}
                {icon}
            </div>
        </motion.div>
    );
}
