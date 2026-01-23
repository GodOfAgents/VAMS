"use client";

import { Github, Twitter, Mail } from "lucide-react";

export function Footer() {
    return (
        <footer className="border-t border-white/10 bg-black pt-24 pb-12">
            <div className="container mx-auto px-4">

                {/* Main CTA */}
                <div className="max-w-4xl mx-auto text-center mb-24">
                    <h2 className="text-4xl md:text-5xl font-display font-bold mb-6">
                        Join the <span className="text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-purple-400">Sovereign Revolution</span>
                    </h2>
                    <p className="text-xl text-gray-400 mb-8">
                        We are opening a 7% Strategic Allocation for partners who share our vision of an agentic future.
                    </p>

                    <div className="flex flex-col sm:flex-row gap-4 justify-center">
                        <button className="px-8 py-4 bg-white text-black font-bold rounded-lg hover:scale-105 transition-transform flex items-center justify-center gap-2">
                            <Mail className="w-5 h-5" />
                            Contact for Allocation
                        </button>
                        <button className="px-8 py-4 bg-white/5 border border-white/10 rounded-lg hover:bg-white/10 transition-colors text-white font-bold flex items-center justify-center gap-2">
                            <Github className="w-5 h-5" />
                            View Architecture
                        </button>
                    </div>
                </div>

                {/* Links Grid */}
                <div className="grid md:grid-cols-4 gap-12 border-t border-white/10 pt-16">
                    <div className="col-span-2">
                        <h3 className="text-2xl font-display font-bold mb-4">VAMS</h3>
                        <p className="text-gray-500 max-w-sm">
                            The &quot;AWS of Web3&quot; for Autonomous AI Agents. <br />
                            Verifiable. Agentic. Modular. Sovereign.
                        </p>
                        <div className="flex gap-4 mt-6">
                            <a href="#" className="p-2 rounded-full bg-white/5 hover:bg-white/10 text-gray-400 hover:text-white transition-colors"><Twitter className="w-5 h-5" /></a>
                            <a href="#" className="p-2 rounded-full bg-white/5 hover:bg-white/10 text-gray-400 hover:text-white transition-colors"><Github className="w-5 h-5" /></a>
                            <a href="#" className="p-2 rounded-full bg-white/5 hover:bg-white/10 text-gray-400 hover:text-white transition-colors"><Mail className="w-5 h-5" /></a>
                        </div>
                    </div>

                    <div>
                        <h4 className="font-bold mb-6">Platform</h4>
                        <ul className="space-y-4 text-gray-500 text-sm">
                            <li><a href="#" className="hover:text-cyan-400 transition-colors">Technology</a></li>
                            <li><a href="#" className="hover:text-cyan-400 transition-colors">Solutions</a></li>
                            <li><a href="#" className="hover:text-cyan-400 transition-colors">Immortal Agents</a></li>
                            <li><a href="#" className="hover:text-cyan-400 transition-colors">Roadmap</a></li>
                        </ul>
                    </div>

                    <div>
                        <h4 className="font-bold mb-6">Resources</h4>
                        <ul className="space-y-4 text-gray-500 text-sm">
                            <li><a href="#" className="hover:text-cyan-400 transition-colors">Whitepaper</a></li>
                            <li><a href="#" className="hover:text-cyan-400 transition-colors">Documentation</a></li>
                            <li><a href="#" className="hover:text-cyan-400 transition-colors">GitHub</a></li>
                            <li><a href="#" className="hover:text-cyan-400 transition-colors">Status</a></li>
                        </ul>
                    </div>
                </div>

                <div className="mt-16 text-center text-gray-600 text-sm">
                    © 2026 VAMS Protocol. All Rights Reserved.
                </div>
            </div>
        </footer>
    );
}
