"use client";

import { motion, useMotionValue, useSpring, useTransform } from "framer-motion";
import { Github, ShieldCheck, Scale, FileCode } from "lucide-react";
import React from "react";

const TiltCard = ({ children, className }: { children: React.ReactNode; className?: string }) => {
    const x = useMotionValue(0);
    const y = useMotionValue(0);

    const mouseXSpring = useSpring(x);
    const mouseYSpring = useSpring(y);

    const rotateX = useTransform(mouseYSpring, [-0.5, 0.5], ["17.5deg", "-17.5deg"]);
    const rotateY = useTransform(mouseXSpring, [-0.5, 0.5], ["-17.5deg", "17.5deg"]);

    const handleMouseMove = (e: React.MouseEvent<HTMLDivElement, MouseEvent>) => {
        const rect = (e.target as HTMLElement).getBoundingClientRect();
        const width = rect.width;
        const height = rect.height;
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;
        const xPct = mouseX / width - 0.5;
        const yPct = mouseY / height - 0.5;
        x.set(xPct);
        y.set(yPct);
    };

    const handleMouseLeave = () => {
        x.set(0);
        y.set(0);
    };

    return (
        <motion.div
            onMouseMove={handleMouseMove}
            onMouseLeave={handleMouseLeave}
            style={{
                rotateY,
                rotateX,
                transformStyle: "preserve-3d",
            }}
            className={`relative h-full transition-all duration-200 ease-out cursor-pointer ${className}`}
        >
            {children}
        </motion.div>
    );
};

export default function TransparencySection() {
    return (
        <section className="relative py-24 bg-[var(--background)] overflow-hidden">
            {/* Background Gradients */}
            <div className="absolute top-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-[var(--color-brand-cyan)] to-transparent opacity-20" />
            <div className="absolute top-[20%] right-[-10%] w-[500px] h-[500px] bg-[var(--color-brand-purple)] opacity-10 blur-[120px] rounded-full pointer-events-none" />

            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="text-center mb-16">
                    <h2 className="text-3xl md:text-5xl font-bold text-white mb-4">
                        Radical Transparency. <br />
                        <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-cyan-300">
                            Verifiable by Design.
                        </span>
                    </h2>
                    <p className="text-gray-400 max-w-2xl mx-auto text-lg">
                        We don&apos;t ask you to trust us. We ask you to verify us. Modular Sovereignty means every line of code
                        and every economic policy is on-chain.
                    </p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                    {/* Pillar 1: Code Transparency */}
                    <TiltCard className="group">
                        <div className="glass-panel h-full p-8 rounded-2xl border border-white/5 hover:border-[var(--color-brand-cyan)]/50 transition-colors">
                            <div className="w-12 h-12 bg-cyan-900/30 rounded-lg flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                                <FileCode className="w-6 h-6 text-cyan-400" />
                            </div>
                            <h3 className="text-xl font-bold text-white mb-3">100% Open Source</h3>
                            <p className="text-gray-400 mb-6">
                                Monorepo structure. No private repositories. Every commit is visible from day one.
                            </p>
                            <div className="flex items-center space-x-2 text-xs font-mono text-cyan-400 bg-cyan-950/30 px-3 py-1 rounded border border-cyan-900/50">
                                <Github className="w-3 h-3" />
                                <span>SHA: 2B1BDDD...</span>
                            </div>
                        </div>
                    </TiltCard>

                    {/* Pillar 2: Execution Transparency */}
                    <TiltCard className="group">
                        <div className="glass-panel h-full p-8 rounded-2xl border border-white/5 hover:border-[var(--color-brand-purple)]/50 transition-colors">
                            <div className="w-12 h-12 bg-purple-900/30 rounded-lg flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                                <ShieldCheck className="w-6 h-6 text-purple-400" />
                            </div>
                            <h3 className="text-xl font-bold text-white mb-3">Verifiable Execution</h3>
                            <p className="text-gray-400">
                                Zero-Knowledge proofs for computation. TEE attestations for private intents. You verify, not just trust.
                            </p>
                        </div>
                    </TiltCard>

                    {/* Pillar 3: Governance Transparency */}
                    <TiltCard className="group">
                        <div className="glass-panel h-full p-8 rounded-2xl border border-white/5 hover:border-pink-500/50 transition-colors">
                            <div className="w-12 h-12 bg-pink-900/30 rounded-lg flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                                <Scale className="w-6 h-6 text-pink-400" />
                            </div>
                            <h3 className="text-xl font-bold text-white mb-3">Immutable Governance</h3>
                            <p className="text-gray-400">
                                Admins are temporary. Contracts are immutable. DAO governance launches Q4 2026.
                            </p>
                        </div>
                    </TiltCard>
                </div>
            </div>
        </section>
    );
}
