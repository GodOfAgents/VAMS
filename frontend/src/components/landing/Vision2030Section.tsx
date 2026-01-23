"use client";

import { motion } from "framer-motion";

export default function Vision2030Section() {
    return (
        <section className="py-32 bg-gradient-to-b from-black to-[var(--background)] relative overflow-hidden">
            {/* Ambient effects */}
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--color-brand-cyan)_0%,_transparent_50%)] opacity-5" />

            <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.8 }}
                >
                    <div className="mb-8">
                        <span className="text-cyan-400 font-mono text-sm tracking-widest uppercase">Vision 2030</span>
                    </div>

                    <h2 className="text-5xl md:text-7xl font-bold text-white mb-8 leading-tight">
                        The Operating System <br />
                        <span className="text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 via-blue-400 to-purple-500">
                            for AGI
                        </span>
                    </h2>

                    <div className="space-y-6 text-xl md:text-2xl text-gray-400 leading-relaxed mb-12">
                        <p>
                            In 5 years, <span className="text-white font-semibold">AI Agents will outnumber humans 100:1</span> on the internet.
                        </p>
                        <p>
                            They will trade, create, and transact <span className="text-white font-semibold">autonomously</span>.
                        </p>
                        <p className="text-gray-500 text-lg">
                            They won&apos;t use Visa. They won&apos;t use AWS.
                        </p>
                    </div>

                    <div className="inline-block">
                        <div className="bg-gradient-to-r from-cyan-500/10 to-purple-500/10 border border-cyan-500/30 rounded-2xl p-8 md:p-12">
                            <p className="text-3xl md:text-4xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-purple-400">
                                VAMS will be the ground they walk on.
                            </p>
                        </div>
                    </div>

                    <div className="mt-16 text-sm text-gray-600 font-mono">
                        Decentralized. Verifiable. Sovereign. Unstoppable.
                    </div>
                </motion.div>
            </div>
        </section>
    );
}
