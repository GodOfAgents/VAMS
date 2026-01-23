"use client";

import { motion } from "framer-motion";
import { LucideIcon, Activity, Server, Database, Cpu, Layout, GitCommit } from "lucide-react";

const StatusMetric = ({ label, percentage, color, icon: Icon }: { label: string; percentage: number; color: string; icon: LucideIcon }) => {
    return (
        <div className="mb-6">
            <div className="flex justify-between items-center mb-2">
                <div className="flex items-center space-x-2 text-gray-300">
                    <Icon className="w-4 h-4 text-gray-500" />
                    <span className="text-sm font-medium tracking-wide uppercase">{label}</span>
                </div>
                <span className={`text-sm font-bold ${color}`}>{percentage}%</span>
            </div>
            <div className="h-2 w-full bg-gray-800 rounded-full overflow-hidden">
                <motion.div
                    initial={{ width: 0 }}
                    whileInView={{ width: `${percentage}%` }}
                    transition={{ duration: 1.5, ease: "easeOut" }}
                    className={`h-full rounded-full ${color.replace("text-", "bg-")}`}
                />
            </div>
        </div>
    );
};

export default function LiveStatusDashboard() {
    return (
        <section className="py-24 bg-black/40 border-y border-white/5 backdrop-blur-sm">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">

                    {/* Left Column: Text Context */}
                    <div>
                        <div className="inline-flex items-center space-x-2 text-green-400 mb-6">
                            <span className="relative flex h-3 w-3">
                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                                <span className="relative inline-flex rounded-full h-3 w-3 bg-green-500"></span>
                            </span>
                            <span className="font-mono text-sm font-bold tracking-wider">SYSTEM STATUS: ONLINE</span>
                        </div>

                        <h2 className="text-4xl font-bold text-white mb-6">
                            Open Heart Engineering. <br />
                            <span className="text-gray-500">Built in public.</span>
                        </h2>

                        <p className="text-xl text-gray-400 mb-8">
                            We ship code, not promises. Track our engineering velocity in real-time directly from our monorepo status.
                        </p>

                        <div className="p-6 bg-white/5 rounded-xl border border-white/10 font-mono text-sm text-gray-400">
                            <div className="flex items-center space-x-2 mb-2 text-white">
                                <GitCommit className="w-4 h-4" />
                                <span>Latest Commit</span>
                            </div>
                            <p className="text-xs break-all text-gray-500">
                                8f304f1b9b3b21979a7fc2d7... (Updated 10 mins ago)
                            </p>
                            <div className="mt-4 pt-4 border-t border-white/10 flex justify-between">
                                <span>Current Phase:</span>
                                <span className="text-yellow-400">Pre-Testnet</span>
                            </div>
                        </div>
                    </div>

                    {/* Right Column: Metrics Dashboard */}
                    <div className="bg-[#0A0A0A] p-8 rounded-2xl border border-white/10 shadow-2xl relative overflow-hidden">
                        {/* Scanline Effect */}
                        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-white/5 to-transparent h-[5px] w-full animate-scan pointer-events-none opacity-20" />

                        <div className="flex justify-between items-center mb-8 border-b border-white/10 pb-4">
                            <h3 className="text-white font-mono text-lg">Engineering Velocity</h3>
                            <Activity className="w-5 h-5 text-gray-500" />
                        </div>

                        <StatusMetric
                            label="Architecture Specification"
                            percentage={100}
                            color="text-emerald-400"
                            icon={Layout}
                        />
                        <StatusMetric
                            label="Tokenomics & Models"
                            percentage={100}
                            color="text-emerald-400"
                            icon={Database}
                        />
                        <StatusMetric
                            label="Agent Logic (Python)"
                            percentage={70}
                            color="text-cyan-400"
                            icon={Cpu}
                        />
                        <StatusMetric
                            label="Smart Contracts"
                            percentage={60}
                            color="text-yellow-400"
                            icon={Server}
                        />
                        <StatusMetric
                            label="Frontend Dashboard"
                            percentage={40}
                            color="text-purple-400"
                            icon={Layout}
                        />

                        <div className="mt-8 pt-6 border-t border-white/10">
                            <p className="text-xs text-center text-gray-600 font-mono">
                                SYNCED WITH REPO_STATUS_REPORT.MD
                            </p>
                        </div>
                    </div>
                </div>
            </div>
        </section>
    );
}
