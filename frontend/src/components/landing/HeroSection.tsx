"use client";

import React, { useState, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Points, PointMaterial } from "@react-three/drei";
import * as THREE from "three";
import { motion } from "framer-motion";
import { ArrowRight, Terminal, Shield } from "lucide-react";
import { cn } from "@/lib/utils";

// Native sphere distribution to avoid maath NaN issues
function generateSpherePositions(count: number, radius: number): Float32Array {
    const positions = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
        const theta = Math.random() * Math.PI * 2;
        const phi = Math.acos(2 * Math.random() - 1);
        const r = Math.cbrt(Math.random()) * radius;

        positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
        positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
        positions[i * 3 + 2] = r * Math.cos(phi);
    }
    return positions;
}

function ParticleNetwork() {
    const ref = useRef<THREE.Points>(null!);
    const [sphere] = useState(() => generateSpherePositions(2000, 1.5));

    useFrame((state, delta) => {
        ref.current.rotation.x -= delta / 10;
        ref.current.rotation.y -= delta / 15;
    });

    return (
        <group rotation={[0, 0, Math.PI / 4]}>
            <Points ref={ref} positions={sphere} stride={3} frustumCulled={false}>
                <PointMaterial
                    transparent
                    color="#00F0FF"
                    size={0.005}
                    sizeAttenuation={true}
                    depthWrite={false}
                    opacity={0.4}
                />
            </Points>
        </group>
    );
}

export default function HeroSection() {
    const [, setIsHovered] = useState(false);

    return (
        <section className="relative min-h-[90vh] w-full flex items-center justify-center overflow-hidden bg-background">
            {/* 3D Background */}
            <div className="absolute inset-0 z-0">
                <Canvas camera={{ position: [0, 0, 1] }}>
                    <ParticleNetwork />
                </Canvas>
            </div>

            {/* Content Overlay */}
            <div className="container mx-auto px-6 z-10 grid lg:grid-cols-2 gap-12 items-center">
                <motion.div
                    initial={{ opacity: 0, x: -30 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.8 }}
                    className="space-y-8"
                >
                    {/* Badge */}
                    <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full glass-panel border border-white/10">
                        <span className="relative flex h-2 w-2">
                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
                            <span className="relative inline-flex rounded-full h-2 w-2 bg-cyan-500"></span>
                        </span>
                        <span className="text-xs font-mono tracking-wider text-cyan-glow uppercase">
                            VAMS Protocol v0.3.0 Live
                        </span>
                    </div>

                    <h1 className="text-5xl md:text-7xl lg:text-8xl font-display font-bold leading-tight">
                        The <span className="text-gradient">Sovereign Brain</span> <br />
                        for AI Agents
                    </h1>

                    <p className="text-lg md:text-xl text-gray-400 max-w-xl font-light leading-relaxed">
                        Unified L3 Meta-Architecture for Verifiable AI Agents.
                        <span className="block mt-2 text-white/60">
                            Modular sovereignty connecting $50B+ of DePIN compute with cryptographic finality.
                        </span>
                    </p>

                    <div className="flex flex-wrap gap-4 pt-4">
                        <button
                            onMouseEnter={() => setIsHovered(true)}
                            onMouseLeave={() => setIsHovered(false)}
                            className="group relative px-8 py-4 bg-white text-black font-bold rounded-xl overflow-hidden transition-all active:scale-95"
                        >
                            <div className="absolute inset-0 bg-gradient-to-r from-cyan-400 to-purple-400 opacity-0 group-hover:opacity-100 transition-opacity" />
                            <div className="relative flex items-center gap-2">
                                Initialize Stack
                                <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                            </div>
                        </button>

                        <button className="px-8 py-4 glass-panel border border-white/10 rounded-xl hover:bg-white/5 transition-all text-white flex items-center gap-2 active:scale-95">
                            <Terminal className="w-5 h-5 text-purple-glow" />
                            View Spec
                        </button>
                    </div>

                    {/* Stats/Proof */}
                    <div className="pt-12 grid grid-cols-2 sm:grid-cols-3 gap-8 border-t border-white/5">
                        <Stat label="Total Nodes" value="1,204" />
                        <Stat label="Sovereign APY" value="18.2%" />
                        <Stat label="Audit Hash" value="SHA-256" isHash />
                    </div>
                </motion.div>

                {/* Visual / Proof of Authorship */}
                <motion.div
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 1, delay: 0.2 }}
                    className="hidden lg:block relative"
                >
                    <div className="relative glass-panel p-8 rounded-3xl border border-white/10 aspect-square flex flex-col items-center justify-center space-y-6 overflow-hidden">
                        {/* Visual Centerpiece (Animated Brain Node) */}
                        <div className="relative w-64 h-64">
                            <div className="absolute inset-0 bg-cyan-glow/10 rounded-full blur-[60px] animate-pulse-glow" />
                            <div className="absolute inset-0 border border-cyan-500/20 rounded-full animate-[spin_20s_linear_infinite]" />
                            <div className="absolute inset-8 border border-purple-500/20 rounded-full animate-[spin_15s_linear_infinite_reverse]" />
                            <div className="absolute inset-0 flex items-center justify-center">
                                <div className="w-32 h-32 rounded-3xl bg-black border border-white/10 flex items-center justify-center transform rotate-45 group">
                                    <Terminal className="w-12 h-12 text-cyan-glow -rotate-45" />
                                </div>
                            </div>
                        </div>

                        <div className="text-center">
                            <h3 className="text-xl font-display font-bold">Proof of Authorship</h3>
                            <p className="text-sm text-gray-500 mt-2 font-mono break-all px-4">
                                5f4dcc3b5aa765d61d8327deb882cf99<br />
                                2b9390ea074b8302db1526437d2f4094
                            </p>
                            <div className="mt-4 inline-flex items-center gap-2 px-3 py-1 bg-green-500/10 rounded-full border border-green-500/20">
                                <Shield className="w-3 h-3 text-green-500" />
                                <span className="text-[10px] text-green-500 font-mono uppercase tracking-tighter">Verified Cryptographically</span>
                            </div>
                        </div>

                        {/* Matrix Decorative Elements */}
                        <div className="absolute top-4 left-4 text-[10px] font-mono text-cyan-glow/20 select-none">
                            {['8f304f1b', '5f4dcc3b', '2b9390ea', '074b8302', 'db152643'].map((code, i) => (
                                <div key={i}> {code} </div>
                            ))}
                        </div>
                    </div>
                </motion.div>
            </div>
        </section>
    );
}

function Stat({ label, value, isHash = false }: { label: string; value: string; isHash?: boolean }) {
    return (
        <div className="space-y-1">
            <p className="text-[10px] font-mono text-gray-500 uppercase tracking-widest">{label}</p>
            <p className={cn("text-2xl font-display font-bold", isHash ? "text-cyan-glow/80 text-sm break-all font-mono" : "text-white")}>
                {value}
            </p>
        </div>
    );
}
