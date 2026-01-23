"use client";

import React, { useRef, useState } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Html, OrbitControls, Float } from "@react-three/drei";
import * as THREE from "three";
import { motion } from "framer-motion";

const layers: { name: string; desc: string; color: string; position: [number, number, number] }[] = [
    {
        name: "Layer 5: Economic",
        desc: "$VAMS, Universal Settlement",
        color: "#BD00FF", // Purple
        position: [0, 2, 0],
    },
    {
        name: "Layer 4: Trust",
        desc: "TEEs, ZK-Proofs, Verification",
        color: "#D946EF", // Fuchsia
        position: [0, 1, 0],
    },
    {
        name: "Layer 3: Logic",
        desc: "DBOS, Durable Execution",
        color: "#00F0FF", // Cyan
        position: [0, 0, 0],
    },
    {
        name: "Layer 2: Compute",
        desc: "io.net, Akash, Render",
        color: "#3B82F6", // Blue
        position: [0, -1, 0],
    },
    {
        name: "Layer 1: Foundation",
        desc: "Celestia, Avalanche, Near",
        color: "#1E293B", // Dark Blue/Slate
        position: [0, -2, 0],
    },
];

function StackLayer({ position, color, name, desc, index }: { position: [number, number, number]; color: string; name: string; desc: string; index: number }) {
    const mesh = useRef<THREE.Mesh>(null);
    const [hovered, setHover] = useState(false);

    useFrame((state) => {
        if (mesh.current) {
            // Gentle floating/wobble independent of the Float container
            mesh.current.rotation.x = Math.sin(state.clock.elapsedTime * 0.5 + index) * 0.05;
            mesh.current.position.y = position[1] + Math.sin(state.clock.elapsedTime * 0.3 + index) * 0.1;
        }
    });

    return (
        <group>
            <mesh
                ref={mesh}
                position={position}
                onPointerOver={() => setHover(true)}
                onPointerOut={() => setHover(false)}
            >
                {/* Glass slab representing the layer */}
                <boxGeometry args={[3.5, 0.4, 3.5]} />
                <meshPhysicalMaterial
                    color={hovered ? "#ffffff" : color}
                    transparent
                    opacity={0.6}
                    roughness={0.1}
                    metalness={0.1}
                    transmission={0.5}
                    thickness={0.5}
                    emissive={color}
                    emissiveIntensity={hovered ? 0.8 : 0.2}
                />
            </mesh>

            {/* Label floating next to the layer */}
            <Html position={[2, position[1], 0]} center transform sprite>
                <div className={`p-3 rounded-lg border backdrop-blur-md transition-all duration-300 w-64 ${hovered ? 'bg-white/10 border-white/50 scale-105' : 'bg-black/40 border-white/10'}`}>
                    <h4 className="text-white font-bold text-sm font-display mb-1" style={{ color: hovered ? color : 'white' }}>{name}</h4>
                    <p className="text-gray-300 text-xs">{desc}</p>
                </div>
            </Html>
        </group>
    );
}

function Scene() {
    return (
        <>
            <ambientLight intensity={0.5} />
            <pointLight position={[10, 10, 10]} intensity={1} color="#00F0FF" />
            <pointLight position={[-10, 5, -10]} intensity={0.5} color="#BD00FF" />

            <Float speed={2} rotationIntensity={0.2} floatIntensity={0.5}>
                <group rotation={[0.2, -0.5, 0]}>
                    {layers.map((layer, i) => (
                        <StackLayer
                            key={i}
                            index={i}
                            name={layer.name}
                            desc={layer.desc}
                            color={layer.color}
                            position={layer.position as [number, number, number]}
                        />
                    ))}
                </group>
            </Float>

            <OrbitControls enableZoom={false} autoRotate autoRotateSpeed={0.5} maxPolarAngle={Math.PI / 2} minPolarAngle={Math.PI / 3} />
        </>
    );
}

export function Technology() {
    return (
        <section className="py-24 bg-deep-space relative overflow-hidden h-[900px]">
            <div className="absolute inset-0 z-0">
                <Canvas camera={{ position: [0, 0, 8], fov: 45 }}>
                    <Scene />
                </Canvas>
            </div>

            {/* Overlay Content */}
            <div className="container mx-auto px-4 relative z-10 pointer-events-none h-full flex flex-col justify-between">
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    className="text-center pt-8"
                >
                    <div className="inline-block px-4 py-1.5 rounded-full border border-purple-500/30 bg-purple-500/10 text-purple-400 text-sm font-mono mb-6">
                        ARCHITECTURE
                    </div>
                    <h2 className="text-4xl md:text-5xl font-display font-bold mb-4">
                        The 5-Layer <span className="text-transparent bg-clip-text bg-gradient-to-r from-cyan-glow to-purple-glow">VAMS Stack</span>
                    </h2>
                    <p className="text-gray-400 text-lg max-w-xl mx-auto">
                        Vertical integration of the best DePIN primitives into a single, cohesive operating system.
                    </p>
                </motion.div>

                <div className="pb-12 text-center">
                    <p className="text-sm text-gray-500 font-mono">
                        Click and drag to interact with the architecture • Powered by WebGL
                    </p>
                </div>
            </div>
        </section>
    );
}
