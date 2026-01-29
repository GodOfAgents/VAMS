import React, { useState, useEffect, useRef, useMemo } from 'react';
import * as THREE from 'three';
import {
  Layers,
  ShieldCheck,
  Database,
  Globe,
  ArrowRight,
  Zap,
  Lock,
  Activity,
  Server,
  Box,
  ChevronDown,
  Cpu,
  Network,
  Code,
  Key,
  FileText,
  Terminal,
  Github,
  Mail,
  Linkedin,
  Twitter,
  Send,

  MousePointer2,
  Scale,
  Unlock,
  Eye,
  DollarSign,
  Sun,
  Moon
} from 'lucide-react';
import vamsLogo from './assets/vams-logo.png';
import aseemProfile from './assets/aseem.jpg';

/* VAMS DESIGN SYSTEM 6.0: Immersive 3D Experiences
   - Added: Section-specific Three.js backgrounds
   - Optimized: Performance with careful rendering loops
   - Preserved: All existing content and logic
*/

// --- 1. UTILITY COMPONENTS ---

const NoiseOverlay = () => (
  <div
    className="fixed inset-0 pointer-events-none z-[100] opacity-[0.03] mix-blend-overlay"
    style={{
      backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.8' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E")`
    }}
  />
);

const MagneticButton = ({ children, className = "", onClick, ariaLabel }) => {
  const btnRef = useRef(null);
  const [position, setPosition] = useState({ x: 0, y: 0 });

  const handleMouseMove = (e) => {
    const { left, top, width, height } = btnRef.current.getBoundingClientRect();
    const x = e.clientX - (left + width / 2);
    const y = e.clientY - (top + height / 2);
    setPosition({ x: x * 0.2, y: y * 0.2 });
  };

  const handleMouseLeave = () => {
    setPosition({ x: 0, y: 0 });
  };

  return (
    <button
      ref={btnRef}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      onClick={onClick}
      aria-label={ariaLabel}
      style={{ transform: `translate(${position.x}px, ${position.y}px)` }}
      className={`transition-transform duration-200 ease-out will-change-transform ${className}`}
    >
      {children}
    </button>
  );
};

// --- 2. THREE.JS BACKGROUNDS (Context-Aware) ---

// 2.1 Hero: Agent Network (Existing)
// 2.1 Hero: The Neural Topography (Organic Data Landscape)
const NeuralTopographyBackground = ({ isDark }) => {
  const mountRef = useRef(null);
  const mouseRef = useRef(new THREE.Vector2(0, 0));

  useEffect(() => {
    if (!mountRef.current) return;
    const container = mountRef.current;

    // --- SETUP ---
    const scene = new THREE.Scene();
    // Subtle fog to fade the horizon - creates depth without hiding the content
    const fogColor = isDark ? 0x050505 : 0xfefefe;
    scene.fog = new THREE.FogExp2(fogColor, 0.035);
    scene.background = new THREE.Color(fogColor);

    const camera = new THREE.PerspectiveCamera(60, container.clientWidth / container.clientHeight, 0.1, 100);
    camera.position.set(0, 5, 12);
    camera.lookAt(0, 0, 0);

    const renderer = new THREE.WebGLRenderer({
      antialias: true, // High fidelity
      alpha: false,
      powerPreference: 'high-performance'
    });
    renderer.setSize(container.clientWidth, container.clientHeight);
    // High pixel ratio for Retina crispness
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 3.0));
    container.appendChild(renderer.domElement);

    // --- GEOMETRY: THE NEURAL MESH ---
    // High-res plane for organic movement
    const planeGeo = new THREE.PlaneGeometry(60, 40, 128, 128);
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', planeGeo.attributes.position);

    const count = geometry.attributes.position.count;

    // Create random grayscale colors for each vertex
    const colors = new Float32Array(count * 3);
    const updateColors = () => {
      for (let i = 0; i < count; i++) {
        let shade;
        if (isDark) {
          // Dark Mode: Soften whites -> Mid-Light Grays (0.2 - 0.7)
          shade = 0.2 + Math.random() * 0.5;
        } else {
          // Light Mode: Soften blacks -> Dark Grays (0.1 - 0.5)
          shade = 0.1 + Math.random() * 0.4;
        }
        colors[i * 3] = shade;
        colors[i * 3 + 1] = shade;
        colors[i * 3 + 2] = shade;
      }
      geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    }
    updateColors();

    // --- MATERIAL: SHIMMERING DATA ---
    // Custom points material for that "tech-organic" look
    const material = new THREE.PointsMaterial({
      size: isDark ? 0.06 : 0.08,
      vertexColors: true,
      transparent: true,
      opacity: isDark ? 0.6 : 0.75, // Reduced from 0.8/0.95 for softer look
      blending: isDark ? THREE.AdditiveBlending : THREE.NormalBlending,
    });

    const points = new THREE.Points(geometry, material);
    points.rotation.x = -Math.PI / 2.5; // Tilted horizon
    scene.add(points);

    // --- SIMPLEX NOISE IMPLEMENTATION (Simplified for perf) ---
    // A pseudo-random noise generator to create the rolling "terrain"
    const perm = new Uint8Array(512);
    const p = new Uint8Array(256);
    for (let i = 0; i < 256; i++) p[i] = i;
    for (let i = 0; i < 256; i++) {
      let r = Math.floor(Math.random() * (256 - i)) + i, t = p[i];
      p[i] = p[r]; p[r] = t;
    }
    for (let i = 0; i < 512; i++) perm[i] = p[i & 255];

    function noise(x, y) { // 2D Simplex Noise
      const F2 = 0.5 * (Math.sqrt(3.0) - 1.0);
      const G2 = (3.0 - Math.sqrt(3.0)) / 6.0;
      let n0, n1, n2;
      let s = (x + y) * F2;
      let i = Math.floor(x + s), j = Math.floor(y + s);
      let t = (i + j) * G2;
      let X0 = i - t, Y0 = j - t;
      let x0 = x - X0, y0 = y - Y0;
      let i1, j1;
      if (x0 > y0) { i1 = 1; j1 = 0; } else { i1 = 0; j1 = 1; }
      let x1 = x0 - i1 + G2, y1 = y0 - j1 + G2;
      let x2 = x0 - 1.0 + 2.0 * G2, y2 = y0 - 1.0 + 2.0 * G2;
      let ii = i & 255, jj = j & 255;
      let gi0 = perm[ii + perm[jj]] % 12, gi1 = perm[ii + i1 + perm[jj + j1]] % 12, gi2 = perm[ii + 1 + perm[jj + 1]] % 12;

      // Fast calculate gradients
      let t0 = 0.5 - x0 * x0 - y0 * y0;
      if (t0 < 0) n0 = 0.0; else { t0 *= t0; n0 = t0 * t0 * ((gi0 < 4 ? x0 : (gi0 == 12 ? x0 : 0)) + (gi0 < 4 ? 0 : y0)); } // Simplified dot
      let t1 = 0.5 - x1 * x1 - y1 * y1;
      if (t1 < 0) n1 = 0.0; else { t1 *= t1; n1 = t1 * t1 * ((gi1 < 4 ? x1 : (gi1 == 12 ? x1 : 0)) + (gi1 < 4 ? 0 : y1)); }
      let t2 = 0.5 - x2 * x2 - y2 * y2;
      if (t2 < 0) n2 = 0.0; else { t2 *= t2; n2 = t2 * t2 * ((gi2 < 4 ? x2 : (gi2 == 12 ? x2 : 0)) + (gi2 < 4 ? 0 : y2)); }

      return 70.0 * (n0 + n1 + n2);
    }

    // --- ANIMATION LOOP ---
    const clock = new THREE.Clock();
    let frameId;

    const animate = () => {
      frameId = requestAnimationFrame(animate);
      const time = clock.getElapsedTime() * 0.4; // Slow, majestic speed

      const positions = geometry.attributes.position.array;

      // Update every vertex to create the rolling wave effect
      for (let i = 0; i < count; i++) {
        const x = positions[i * 3];
        const y = positions[i * 3 + 1]; // This is actually Z in world space due to rotation

        // Base rolling terrain
        let z = noise(x * 0.1 + time, y * 0.1);

        // Detail layer (higher frequency)
        z += noise(x * 0.3 - time, y * 0.3) * 0.3;

        // Interaction: "Searchlight" effect
        // Lift terrain near mouse cursor
        const dx = x - (mouseRef.current.x * 40);
        const dy = y - (-mouseRef.current.y * 30);
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 10) {
          z += (10 - dist) * 0.5; // Smoothly raise up
        }

        // Apply height map
        positions[i * 3 + 2] = z;
      }
      geometry.attributes.position.needsUpdate = true;
      geometry.computeVertexNormals(); // Recalculate for lighting effects (if we added lights later)

      // Slow camera drift for cinematic feel
      camera.position.x = Math.sin(time * 0.1) * 2;
      camera.lookAt(0, 0, 0);

      renderer.render(scene, camera);
    };

    animate();

    const handleResize = () => {
      if (!container) return;
      camera.aspect = container.clientWidth / container.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(container.clientWidth, container.clientHeight);
    };

    const handleMouseMove = (e) => {
      // Normalize mouse coordinates -1 to +1
      const rect = container.getBoundingClientRect();
      mouseRef.current.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      // Fix Y-axis inversion: remove the negative sign
      mouseRef.current.y = ((e.clientY - rect.top) / rect.height) * 2 - 1;
    };

    const handleTouchMove = (e) => {
      if (e.touches.length > 0) {
        const touch = e.touches[0];
        const rect = container.getBoundingClientRect();
        mouseRef.current.x = ((touch.clientX - rect.left) / rect.width) * 2 - 1;
        mouseRef.current.y = ((touch.clientY - rect.top) / rect.height) * 2 - 1;
      }
    };

    window.addEventListener('resize', handleResize);
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('touchmove', handleTouchMove, { passive: true });
    window.addEventListener('touchstart', handleTouchMove, { passive: true });

    return () => {
      window.removeEventListener('resize', handleResize);
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('touchmove', handleTouchMove);
      window.removeEventListener('touchstart', handleTouchMove);
      cancelAnimationFrame(frameId);
      renderer.dispose();
      if (container && renderer.domElement.parentNode === container) {
        container.removeChild(renderer.domElement);
      }
    };
  }, [isDark]);

  return <div ref={mountRef} className="fixed inset-0 z-0 pointer-events-none transition-opacity duration-1000" />;
};

// --- 3. UI COMPONENTS (SEO & VISIBILITY OPTIMIZED) ---

const SmokeHeader = ({ text, className = "", tag = "h2", isDark }) => {
  const [isVisible, setIsVisible] = useState(false);
  const elementRef = useRef(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) setIsVisible(true);
      },
      { threshold: 0.1, rootMargin: "-50px" }
    );
    if (elementRef.current) observer.observe(elementRef.current);
    return () => { if (elementRef.current) observer.unobserve(elementRef.current); };
  }, []);

  const words = text.split(" ");
  const Tag = tag;
  const colorClass = isDark ? "text-gray-100" : "text-gray-900";

  let globalLetterIdx = 0;

  return (
    <Tag ref={elementRef} className={`relative flex flex-wrap gap-x-[0.3em] ${className} ${colorClass}`} aria-label={text}>
      {words.map((word, wordIndex) => {
        const letters = word.split("");
        return (
          <span key={wordIndex} className="inline-block whitespace-nowrap" aria-hidden="true">
            {letters.map((letter, i) => {
              const delay = globalLetterIdx * 35;
              globalLetterIdx++;
              return (
                <span
                  key={i}
                  className="inline-block will-change-transform will-change-filter"
                  style={{
                    transition: 'all 1s cubic-bezier(0.2, 0.65, 0.3, 0.9)',
                    transitionDelay: `${delay}ms`,
                    opacity: isVisible ? 1 : 0,
                    filter: isVisible ? 'blur(0px)' : 'blur(12px)',
                    transform: isVisible ? 'translateY(0) scale(1)' : 'translateY(20px) scale(1.15)',
                  }}
                >
                  {letter}
                </span>
              );
            })}
          </span>
        );
      })}
    </Tag>
  );
};

const SectionWrapper = ({ children, id, className = "" }) => (
  <section id={id} className={`relative py-24 md:py-32 px-6 md:px-12 max-w-7xl mx-auto ${className}`}>
    {children}
  </section>
);

const Divider = ({ isDark }) => <div className={`w-full h-px ${isDark ? 'bg-gray-800' : 'bg-gray-200'} transition-colors duration-500`} role="presentation" />;

// --- 4. MAIN PAGE CONTENT ---

export default function VAMS_Web3_Guild() {
  console.log("VAMS App Initializing...");
  const [scrolled, setScrolled] = useState(false);
  const [isDark, setIsDark] = useState(true);

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 50);
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const toggleTheme = () => setIsDark(!isDark);

  // Dynamic Styles
  const bgMain = isDark ? 'bg-[#0a0a0a]' : 'bg-white';
  const textMain = isDark ? 'text-gray-100' : 'text-gray-900';
  const textSub = isDark ? 'text-gray-400' : 'text-gray-600';
  const borderLight = isDark ? 'border-gray-800' : 'border-gray-200';
  const borderHover = isDark ? 'hover:border-gray-500' : 'hover:border-black';
  const bgAlt = isDark ? 'bg-[#111111]' : 'bg-gray-50';
  const navBg = scrolled
    ? (isDark ? 'bg-[#0a0a0a]/60 border-white/10' : 'bg-white/60 border-black/5')
    : 'bg-transparent border-transparent';

  return (
    <main className={`min-h-screen font-sans selection:bg-purple-500 selection:text-white cursor-default transition-colors duration-700 ${bgMain} ${textMain}`}>
      <NoiseOverlay />

      {/* Navigation */}
      <nav className={`fixed top-0 w-full z-[90] transition-all duration-500 border-b backdrop-blur-xl ${navBg} py-1.5`} aria-label="Main Navigation">
        <div className="max-w-7xl mx-auto px-6 md:px-12 flex justify-between items-center">
          <div className="flex items-center cursor-pointer">
            <img
              src={vamsLogo}
              alt="VAMS Logo"
              className="h-16 w-auto object-contain"
            />
          </div>

          <div className={`hidden md:flex gap-12 text-[10px] font-mono uppercase tracking-[0.15em] font-medium ${textSub}`}>
            {['Vision', 'Manifesto', 'Stack'].map((item) => (
              <a key={item} href={`#${item.toLowerCase()}`} className={`hover:${isDark ? 'text-white' : 'text-black'} transition-colors relative group`}>
                {item}
                <span className={`absolute -bottom-1 left-0 w-0 h-px ${isDark ? 'bg-white' : 'bg-black'} transition-all group-hover:w-full`}></span>
              </a>
            ))}
          </div>

          <div className="flex items-center gap-4">
            <button
              onClick={toggleTheme}
              className={`p-2 rounded-full border ${borderLight} ${borderHover} transition-all duration-300 group`}
              aria-label={isDark ? "Switch to Light Mode" : "Switch to Dark Mode"}
            >
              {isDark ? (
                <Sun size={14} className="text-gray-200 group-hover:rotate-90 transition-transform duration-500" />
              ) : (
                <Moon size={14} className="text-gray-900 group-hover:-rotate-12 transition-transform duration-500" />
              )}
            </button>

            <span className={`hidden lg:flex items-center gap-2 font-mono text-[9px] uppercase tracking-widest text-green-500 border border-green-500/20 bg-green-500/10 px-3 py-1 rounded-full`}>
              <span className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse"></span>
              System Normal
            </span>
            <a
              href="https://github.com/GodOfAgents/VAMS"
              target="_blank"
              rel="noopener noreferrer"
              className={`hidden md:flex items-center gap-2 border ${borderLight} px-5 py-2.5 text-[10px] font-mono uppercase tracking-widest ${borderHover} ${isDark ? 'hover:bg-white hover:text-black' : 'hover:bg-black hover:text-white'} transition-all duration-300 rounded-[9px]`}
              aria-label="View VAMS on GitHub"
            >
              <Github size={10} aria-hidden="true" />
              <span>VAMS on GitHub</span>
            </a>
          </div>
        </div>
      </nav>

      {/* HERO SECTION */}
      <header className="relative min-h-screen flex items-center overflow-hidden">
        <NeuralTopographyBackground isDark={isDark} />

        <div className="relative z-10 max-w-7xl mx-auto px-6 md:px-12 pt-20">
          <div className="flex items-center gap-4 mb-10 animate-fade-in-up" style={{ animationDelay: '0.2s' }}>
            <span className={`h-px w-12 ${isDark ? 'bg-gray-400' : 'bg-black'}`}></span>
            <h2 className={`font-mono text-[10px] uppercase tracking-[0.25em] ${textSub} font-semibold`}>Verifiable Agentic Modular Stack</h2>
          </div>

          <div className="space-y-4 mb-16">
            <SmokeHeader
              text="Infrastructure for"
              tag="h1"
              isDark={isDark}
              className={`font-serif text-4xl md:text-7xl lg:text-[7rem] leading-[0.9] tracking-tight ${isDark ? 'text-[#DEE2E6]' : ''}`}
            />
            <div className={`font-serif text-4xl md:text-7xl lg:text-[7rem] leading-[0.9] italic tracking-tight ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
              <SmokeHeader
                text="The Agentic Economy"
                tag="span"
                isDark={isDark}
                className={isDark ? 'text-white' : 'text-gray-400'}
              />
            </div>
          </div>

          <p className={`font-sans text-lg md:text-xl ${textSub} max-w-xl leading-relaxed tracking-wide border-l-2 ${borderLight} pl-8 mt-12 mb-16 animate-fade-in-up`} style={{ animationDelay: '0.8s' }}>
            A unified Layer 3 meta-architecture connecting $50B+ of fragmented DePIN infrastructure into a single, consumable API for autonomous software.
          </p>

          <div className="flex flex-col sm:flex-row gap-6 animate-fade-in-up" style={{ animationDelay: '1s' }}>
            <MagneticButton
              ariaLabel="Go to Live Neuron"
              onClick={() => document.getElementById('neuron').scrollIntoView({ behavior: 'smooth' })}
              className={`group relative overflow-hidden ${isDark ? 'bg-white text-black hover:bg-gray-200' : 'bg-black text-white hover:bg-gray-800'} px-10 py-5 font-mono text-xs uppercase tracking-widest shadow-xl transition-all rounded-[9px]`}>
              <span className="relative z-10 flex items-center gap-3">
                Live Neuron <ArrowRight size={14} className="group-hover:translate-x-1 transition-transform" />
              </span>
            </MagneticButton>
            <a href="https://drive.google.com/file/d/1H6tKKyeqczKr6pmsdqSGdYPrrA4oGr0R/" target="_blank" rel="noopener noreferrer">
              <MagneticButton
                ariaLabel="Read Whitepaper"
                className={`flex items-center gap-3 border ${borderLight} px-10 py-5 font-mono text-xs uppercase tracking-widest ${borderHover} transition-colors bg-opacity-40 backdrop-blur-sm rounded-[9px]`}>
                Read Whitepaper v1.0
              </MagneticButton>
            </a>
          </div>
        </div>

        <div className={`absolute bottom-12 left-0 w-full flex justify-center animate-bounce ${isDark ? 'opacity-20' : 'opacity-40'}`} aria-hidden="true">
          <ChevronDown className="text-gray-400" />
        </div>
      </header>

      <Divider isDark={isDark} />

      {/* SECTION: LIVE NEURON DEMO */}
      <section id="neuron" className={`py-32 px-6 md:px-12 relative overflow-hidden transition-colors duration-700 ${bgMain}`}>
        <div className="max-w-7xl mx-auto grid md:grid-cols-2 gap-16 items-center">
          {/* Left Content */}
          <div>
            <div className="flex items-center gap-2 mb-6">
              <div className={`w-2 h-2 rounded-full ${isDark ? 'bg-green-500' : 'bg-green-600'} animate-pulse`}></div>
              <span className={`font-mono text-[10px] uppercase tracking-[0.2em] ${textSub}`}>System Online</span>
            </div>
            <SmokeHeader text="Run a VAMS Neuron" isDark={isDark} className="font-serif text-5xl md:text-6xl mb-6 block" />
            <p className={`${textSub} text-lg leading-relaxed mb-8 max-w-md`}>
              Don't trust, verify. Deploy the immortal agent runtime locally to monitor Data Availability, Compute, and Logic integrity in real-time.
            </p>

            <div className="space-y-4">
              {[
                { label: "Identity", val: "ECDSA / Secp256k1" },
                { label: "Failover", val: "Automatic ( < 100ms )" },
                { label: "Telemetry", val: "Signed Heartbeats" }
              ].map((item, i) => (
                <div key={i} className={`flex items-center justify-between py-3 border-b ${borderLight} max-w-sm`}>
                  <span className={`font-mono text-xs uppercase ${textSub} tracking-wider`}>{item.label}</span>
                  <span className={`font-mono text-xs ${isDark ? 'text-white' : 'text-black'}`}>{item.val}</span>
                </div>
              ))}
            </div>

            <div className="mt-10">
              <a href="https://github.com/GodOfAgents/VAMS/tree/main/neuron" target="_blank" rel="noopener noreferrer">
                <MagneticButton className={`border ${borderLight} px-8 py-4 font-mono text-xs uppercase rounded-[9px] ${isDark ? 'hover:bg-white hover:text-black' : 'hover:bg-black hover:text-white'} transition-colors`}>
                  Get Neuron Code
                </MagneticButton>
              </a>
            </div>
          </div>

          {/* Right: Terminal */}
          <div className={`relative rounded-xl overflow-hidden shadow-2xl border ${isDark ? 'border-gray-800 bg-[#0c0c0c]' : 'border-gray-300 bg-gray-50'}`}>
            <div className={`flex items-center gap-2 px-4 py-3 border-b ${isDark ? 'border-gray-800 bg-gray-900/50' : 'border-gray-200 bg-gray-100'}`}>
              <div className="flex gap-1.5">
                <div className="w-2.5 h-2.5 rounded-full bg-red-500/80"></div>
                <div className="w-2.5 h-2.5 rounded-full bg-yellow-500/80"></div>
                <div className="w-2.5 h-2.5 rounded-full bg-green-500/80"></div>
              </div>
              <div className={`ml-4 font-mono text-[10px] ${textSub}`}>user@vams-node:~/neuron</div>
            </div>

            <div className="p-6 font-mono text-xs md:text-sm leading-loose">
              <div className="text-gray-500">$ python neuron.py --full-health</div>
              <div className="text-blue-400 mt-2">[INFO] VAMS Neuron v0.5.0 initialized</div>
              <div className="text-gray-400">[INFO] Loading identity from node_identity.pem...</div>
              <div className="text-green-400">[SUCCESS] Identity loaded: 0x7f3...9a1</div>

              <div className="mt-4 space-y-1">
                <div className="flex gap-3">
                  <span className="text-gray-500">[CHECK]</span>
                  <span className={isDark ? "text-gray-300" : "text-gray-700"}>Layer 1: Celestia DA</span>
                  <span className="text-green-500 flex-1 text-right">OK (12ms)</span>
                </div>
                <div className="flex gap-3">
                  <span className="text-gray-500">[CHECK]</span>
                  <span className={isDark ? "text-gray-300" : "text-gray-700"}>Layer 2: io.net Compute</span>
                  <span className="text-green-500 flex-1 text-right">OK (GP-GPU)</span>
                </div>
                <div className="flex gap-3">
                  <span className="text-gray-500">[CHECK]</span>
                  <span className={isDark ? "text-gray-300" : "text-gray-700"}>Layer 3: DBOS Logic</span>
                  <span className="text-green-500 flex-1 text-right">OK (Synced)</span>
                </div>
                <div className="flex gap-3">
                  <span className="text-gray-500">[CHECK]</span>
                  <span className={isDark ? "text-gray-300" : "text-gray-700"}>Layer 4: Phala TEE</span>
                  <span className="text-green-500 flex-1 text-right">OK (Secure)</span>
                </div>
              </div>

              <div className="mt-4 text-green-400 font-bold">
                [SUCCESS] Agent Status: IMMORTAL
              </div>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-gray-500 animate-pulse">_</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <Divider isDark={isDark} />

      {/* SECTION 1: VISION & MISSION - Neural Globe BG */}
      <div className="relative overflow-hidden">

        <SectionWrapper id="vision" className="!py-32 relative z-10">
          <div className="grid md:grid-cols-12 gap-16 items-start">
            <article className="md:col-span-5">
              <span className={`font-mono text-[10px] uppercase ${textSub} tracking-[0.2em] mb-4 block`}>Vision 2030</span>
              <SmokeHeader text="The Operating System for AGI" isDark={isDark} className="font-serif text-5xl leading-tight mb-8 block" />
              <div className={`h-1 w-24 ${isDark ? 'bg-white' : 'bg-black'} mb-8`}></div>
            </article>

            <article className="md:col-span-7 space-y-8">
              <p className={`font-serif text-2xl md:text-3xl leading-relaxed tracking-wide ${textMain}`}>
                In 5 years, AI Agents will outnumber humans on Chains 100:1. They won't use Visa. They won't use AWS. They will use verifiable, decentralized, sovereign infrastructure.
              </p>
              <p className={`font-mono text-sm ${textSub} uppercase tracking-widest border-l-2 ${borderLight} pl-4`}>
                Mission: To be the backbone of the Agentic Economy by 2030.
              </p>
            </article>
          </div>
        </SectionWrapper>
      </div>

      {/* SECTION 2: THE PARADIGM SHIFT - Data Flow BG */}
      <section id="manifesto" className={`${bgAlt} py-32 border-y ${borderLight} relative overflow-hidden transition-colors duration-700`}>

        <div className="max-w-7xl mx-auto px-6 md:px-12 relative z-10">
          <header className="mb-20">
            <span className="font-mono text-[10px] uppercase text-red-600 tracking-[0.2em] mb-4 block font-bold">The Great Filter</span>
            <SmokeHeader text="Paradigm Shift" isDark={isDark} className="font-serif text-4xl md:text-6xl mb-6 block" />
            <p className={`max-w-2xl ${textSub} tracking-wide`}>
              The transition from Human-Centric Web2 to Agentic Web3 requires a fundamental infrastructure overhaul.
            </p>
          </header>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {[
              {
                title: "DePIN Utility Crisis",
                web2: "Fragmented Resources",
                vams: "Utilization Layer",
                desc: "Billions in hardware, zero usability. VAMS aggregates it all.",
                icon: Layers,
                span: "md:col-span-2"
              },
              {
                title: "Developer Onboarding",
                web2: "1% Web3 Native",
                vams: "99% Web2 Native",
                desc: "We bridge the gap. Use Python, get sovereign infra.",
                icon: Code,
                span: "md:col-span-1"
              },
              {
                title: "Agent Evolution",
                web2: "Beta / Fragile",
                vams: "Alpha / Immortal",
                desc: "Web2 agents die; VAMS agents persist forever.",
                icon: ShieldCheck,
                span: "md:col-span-1"
              },
              {
                title: "AI Verification",
                web2: "Black Box",
                vams: "Verifiable",
                desc: "Cryptographic proof of inference. Don't trust, verify.",
                icon: Eye,
                span: "md:col-span-1"
              },
              {
                title: "Censorship Resistance",
                web2: "Platform Risk",
                vams: "Unstoppable",
                desc: "Sovereign execution that no corporation can turn off.",
                icon: Unlock,
                span: "md:col-span-2"
              },
              {
                title: "Cost Efficiency",
                web2: "AWS Premium",
                vams: "-80% Costs",
                desc: "Market-based pricing. No monopolistic markups.",
                icon: DollarSign,
                span: "md:col-span-1"
              },
              {
                title: "Research Freedom",
                web2: "Geopolitics",
                vams: "Neutral Ground",
                desc: "Permissionless research labs unaffected by borders.",
                icon: Globe,
                span: "md:col-span-2"
              },
              {
                title: "Payment Rails",
                web2: "Visa / Stripe",
                vams: "Machine Money",
                desc: "Micropayments (x402) designed for software, not humans.",
                icon: Zap,
                span: "md:col-span-2"
              }
            ].map((item, i) => (
              <article
                key={i}
                className={`${item.span} relative group p-8 rounded-[9px] border ${isDark ? 'border-gray-800 bg-[#0c0c0c]' : 'border-gray-200 bg-white'} hover:border-gray-500 transition-all duration-500 overflow-hidden flex flex-col justify-between`}
              >
                {/* Hover Gradient (Monochrome) */}
                <div className={`absolute inset-0 bg-gradient-to-br ${isDark ? 'from-white/5 to-transparent' : 'from-black/5 to-transparent'} opacity-0 group-hover:opacity-100 transition-opacity duration-500`} />

                {/* Icon Background */}
                <div className="absolute -right-4 -top-4 opacity-[0.03] group-hover:opacity-10 transition-opacity duration-500 rotate-12">
                  <item.icon size={120} />
                </div>

                <div className="relative z-10">
                  <div className="flex items-center justify-between mb-6">
                    <div className={`p-2 rounded-lg ${isDark ? 'bg-white/5' : 'bg-black/5'}`}>
                      <item.icon className="w-5 h-5" />
                    </div>
                    <span className="font-mono text-[9px] opacity-40">0{i + 1}</span>
                  </div>

                  <h3 className="font-serif text-2xl md:text-3xl mb-3">{item.title}</h3>
                  <p className={`text-sm ${textSub} mb-8 leading-relaxed max-w-[90%]`}>{item.desc}</p>
                </div>

                <div className="relative z-10 mt-auto">
                  <div className={`flex justify-between items-center text-xs font-mono p-3 rounded-lg ${isDark ? 'bg-black/20' : 'bg-white/40'}`}>
                    <span className="opacity-50 line-through decoration-red-500/50">{item.web2}</span>
                    <ArrowRight size={10} className="opacity-30" />
                    <span className={isDark ? 'text-green-400' : 'text-green-600'}>{item.vams}</span>
                  </div>
                </div>
              </article>
            ))}
            {/* CTA Card */}
            {/* CTA Card: Discord (Monochrome) */}
            <div className={`md:col-span-4 relative group p-10 rounded-[9px] border ${isDark ? 'border-gray-800' : 'border-gray-200'} ${isDark ? 'bg-white' : 'bg-black'} overflow-hidden flex flex-col md:flex-row items-center justify-between gap-8 transition-all duration-500 mt-4`}>

              <div className="text-center md:text-left z-10">
                <h3 className={`${isDark ? 'text-black' : 'text-white'} font-serif text-2xl md:text-3xl mb-2`}>Join the Guild</h3>
                <p className={`${isDark ? 'text-gray-600' : 'text-gray-300'} text-sm font-mono uppercase tracking-widest`}>
                  Community & Builder Access
                </p>
              </div>

              <div className="relative z-10">
                <a
                  href="https://discord.gg/Kp2PpXfkV"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <MagneticButton
                    ariaLabel="Enter Discord"
                    className={`${isDark ? 'bg-black text-white hover:bg-gray-900' : 'bg-white text-black hover:bg-gray-100'} px-8 py-4 font-mono text-xs uppercase tracking-widest rounded-[9px] flex items-center gap-3 transition-colors`}
                  >
                    <span>Enter Discord</span>
                    <ArrowRight size={14} />
                  </MagneticButton>
                </a>
              </div>

              {/* Decorative Background Elements */}
              <div className={`absolute top-0 right-0 w-64 h-64 ${isDark ? 'bg-gray-100' : 'bg-gray-900'} rounded-full blur-3xl -mr-32 -mt-32 opacity-50 pointer-events-none`} />
            </div>
          </div>
        </div>
      </section>

      {/* SECTION 3: THE 5-LAYER STACK */}
      <SectionWrapper id="stack">
        <header className="mb-24">
          <span className={`font-mono text-[10px] uppercase ${textSub} tracking-[0.2em] mb-4 block`}>The Technology</span>
          <SmokeHeader text="The 5-Layer Stack" isDark={isDark} className="font-serif text-4xl md:text-6xl mb-6 block" />
          <p className={`max-w-2xl ${textSub} leading-relaxed font-light text-lg tracking-wide`}>
            We don't just aggregate; we vertically integrate essential primitives into a unified operating system. The "AWS" for software agents.
          </p>
        </header>

        <div className={`space-y-0 border-t ${borderLight}`}>
          {[
            {
              id: "01",
              layer: "Foundational",
              tech: "Celestia / EigenDA",
              desc: "Data Availability Sampling (DAS) & Settlement. The bedrock handling transaction ordering and state management.",
              icon: Box
            },
            {
              id: "02",
              layer: "Compute",
              tech: "io.net / Akash / Render",
              desc: "Sourcing H100 GPU clusters and CPU resources for high-intensity AI inference. Intelligence-as-a-service.",
              icon: Cpu
            },
            {
              id: "03",
              layer: "Logic",
              tech: "DBOS / Kwil / WeaveDB",
              desc: "Crash-proof workflows. Provides exactly-once execution semantics and persistent state management for 'Immortal Agents'.",
              icon: Code
            },
            {
              id: "04",
              layer: "Trust",
              tech: "Phala / Marlin (TEE)",
              desc: "Privacy & Verification. Intel SGX Enclaves ensure computation integrity and confidentiality for sensitive payloads.",
              icon: Lock
            },
            {
              id: "05",
              layer: "Economic",
              tech: "$VAMS / x402 Protocol",
              desc: "Incentives & Agent Commerce. A unified payment gateway enabling machine-to-machine micropayments.",
              icon: Globe
            },
          ].map((layer, i) => (
            <article key={i} className={`group relative grid md:grid-cols-12 p-8 md:p-12 border-b ${borderLight} hover:bg-white/10 hover:backdrop-blur-[2px] transition-all duration-300 cursor-default`}>
              {/* Reveal line on hover */}
              <div className={`absolute left-0 top-0 bottom-0 w-1 ${isDark ? 'bg-white' : 'bg-black'} transform scale-y-0 group-hover:scale-y-100 transition-transform duration-300 origin-top`}></div>

              <div className={`md:col-span-1 font-mono text-sm ${isDark ? 'text-gray-500 group-hover:text-white' : 'text-gray-300 group-hover:text-black'} transition-colors pt-1`}>{layer.id}</div>
              <div className="md:col-span-3 flex items-start gap-4 mb-4 md:mb-0">
                <layer.icon className={`w-5 h-5 mt-1 ${isDark ? 'text-gray-500 group-hover:text-white' : 'text-gray-400 group-hover:text-black'} transition-colors`} aria-hidden="true" />
                <h3 className="font-serif text-2xl group-hover:translate-x-2 transition-transform duration-300">{layer.layer}</h3>
              </div>
              <div className={`md:col-span-3 font-mono text-[10px] uppercase tracking-wider ${textSub} pt-2 mb-4 md:mb-0`}>
                <span className={`border ${borderLight} px-2 py-1 ${isDark ? 'bg-black text-gray-300' : 'bg-white text-gray-600'} group-hover:border-gray-400 transition-colors`}>{layer.tech}</span>
              </div>
              <div className={`md:col-span-5 ${textSub} leading-relaxed text-sm tracking-wide`}>
                {layer.desc}
              </div>
            </article>
          ))}
        </div>
      </SectionWrapper>

      {/* SECTION 4: DEEP TECH (CLR) */}
      <section id="router" className="bg-black text-white py-32 px-6 md:px-12 relative overflow-hidden border-t border-gray-900">
        <div className="absolute inset-0 z-0 opacity-10"
          style={{ backgroundImage: 'linear-gradient(#333 1px, transparent 1px), linear-gradient(90deg, #333 1px, transparent 1px)', backgroundSize: '40px 40px' }}>
        </div>

        <div className="max-w-7xl mx-auto relative z-10">
          <div className="grid md:grid-cols-2 gap-24">
            <div>
              <div className="flex items-center gap-2 mb-8 text-white/50">
                <Network size={16} aria-hidden="true" />
                <span className="font-mono text-[10px] uppercase tracking-[0.2em]">Core Innovation</span>
              </div>
              <SmokeHeader text="Conditional L1 Router" tag="h2" isDark={false} className="font-serif text-4xl md:text-6xl mb-8 block text-white" />
              <p className="text-xl text-gray-400 font-light leading-relaxed mb-16 max-w-lg tracking-wide">
                A ZK-verified engine that dynamically routes transactions based on a deterministic 4-step logic gate.
              </p>

              <div className="relative space-y-0" role="list" aria-label="Routing Steps">
                <div className="absolute left-[19px] top-4 bottom-4 w-px bg-white/10"></div>
                {[
                  { step: "01", label: "Privacy Check", val: "TEE / ZK Required?" },
                  { step: "02", label: "Value Analysis", val: "Tx > $10k USD?" },
                  { step: "03", label: "Sovereignty", val: "Custom VM Needed?" },
                  { step: "04", label: "Velocity", val: "Sub-second Routing" }
                ].map((s, i) => (
                  <div key={i} className="relative flex items-center gap-8 py-6 group" role="listitem">
                    <div className="w-10 h-10 rounded-full border border-white/20 bg-black flex items-center justify-center relative z-10 group-hover:border-white transition-colors">
                      <span className="font-mono text-[10px] text-white/50">{s.step}</span>
                    </div>
                    <div className="flex-1 flex items-center justify-between border-b border-white/10 pb-6 group-hover:border-white/30 transition-colors">
                      <span className="font-serif text-xl">{s.label}</span>
                      <div className="flex items-center gap-3">
                        <span className="font-mono text-[10px] text-green-400 uppercase tracking-wider bg-green-900/20 px-2 py-1 rounded">{s.val}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <aside className="relative border border-white/10 bg-white/5 p-12 backdrop-blur-sm flex flex-col justify-between">
              <div className="absolute top-0 right-0 w-32 h-32 border-t border-r border-white/10"></div>
              <div className="absolute bottom-0 left-0 w-32 h-32 border-b border-l border-white/10"></div>

              <div>
                <h3 className="font-mono text-[10px] text-white/40 uppercase tracking-[0.2em] mb-12">Dual-Chain Architecture</h3>

                <div className="space-y-12">
                  <div className="group cursor-default">
                    <div className="flex items-center gap-4 mb-3">
                      <div className="w-2 h-2 bg-purple-500 rounded-full group-hover:animate-ping"></div>
                      <h4 className="text-2xl md:text-3xl font-serif">Polygon CDK</h4>
                    </div>
                    <div className="text-sm text-gray-500 mb-4 pl-6 font-mono uppercase tracking-wide">Primary L3 Layer</div>
                    <p className="text-gray-400 text-sm leading-relaxed pl-6 border-l border-white/10 tracking-wide">
                      Used for broad liquidity access via AggLayer. Ideal for DeFi agents and general purpose tasks needing Ethereum security guarantees.
                    </p>
                  </div>

                  <div className="group cursor-default">
                    <div className="flex items-center gap-4 mb-3">
                      <div className="w-2 h-2 bg-red-500 rounded-full group-hover:animate-ping"></div>
                      <h4 className="text-2xl md:text-3xl font-serif">Avalanche L1s</h4>
                    </div>
                    <div className="text-sm text-gray-500 mb-4 pl-6 font-mono uppercase tracking-wide">Secondary Sovereign Layer</div>
                    <p className="text-gray-400 text-sm leading-relaxed pl-6 border-l border-white/10 tracking-wide">
                      "Sovereign AI" custom VMs. Agents can control the entire vertical stack with pay-as-you-go dynamic fees (ACP-77).
                    </p>
                  </div>
                </div>
              </div>

              <div className="mt-12 pt-8 border-t border-white/10 flex justify-between items-end text-xs font-mono text-white/30">
                <span>Latency: ~400ms</span>
                <span>Throughput: Unlimited</span>
              </div>
            </aside>
          </div>
        </div>
      </section>

      {/* SECTION 5: TOKENOMICS - Orbital BG */}
      <div className="relative overflow-hidden">

        <SectionWrapper id="tokenomics" className="relative z-10">
          <header className="flex flex-col items-center text-center max-w-3xl mx-auto mb-20">
            <span className={`font-mono text-[10px] uppercase ${textSub} tracking-[0.2em] mb-4 block`}>Economic Model</span>
            <SmokeHeader text="$VAMS Tokenomics" isDark={isDark} className={`font-serif text-4xl md:text-6xl mb-8 block text-center mx-auto ${isDark ? 'text-[#DEE2E6]' : ''}`} />
            <p className={`${textSub} font-light text-lg tracking-wide text-center`}>
              Designed for maximum value accrual and deflationary pressure. <br />We generate revenue from utility, not speculation.
            </p>
          </header>

          <div className="grid md:grid-cols-3 gap-8 mb-24">
            <div className={`bg-white/10 backdrop-blur-[2px] p-10 border ${borderLight} text-center ${borderHover} transition-all duration-300 group`}>
              <div className="font-serif text-5xl mb-4 group-hover:scale-110 transition-transform duration-300">1B</div>
              <div className={`font-mono text-[10px] uppercase tracking-[0.2em] ${textSub}`}>Fixed Supply</div>
            </div>
            <div className={`bg-white/10 backdrop-blur-[2px] p-10 border ${borderLight} text-center ${borderHover} transition-all duration-300 group`}>
              <div className="font-serif text-5xl mb-4 group-hover:scale-110 transition-transform duration-300">100%</div>
              <div className={`font-mono text-[10px] uppercase tracking-[0.2em] ${textSub}`}>Fee Buyback & Burn</div>
            </div>
            <div className={`bg-white/10 backdrop-blur-[2px] p-10 border ${borderLight} text-center ${borderHover} transition-all duration-300 group`}>
              <div className="font-serif text-5xl mb-4 group-hover:scale-110 transition-transform duration-300">4 Year</div>
              <div className={`font-mono text-[10px] uppercase tracking-[0.2em] ${textSub}`}>Founder Vesting</div>
            </div>
          </div>

          <div className="grid md:grid-cols-2 gap-16 items-start">
            <div>
              <h3 className="font-serif text-2xl mb-8 flex items-center gap-3">
                Revenue Streams
                <div className={`h-px flex-1 ${isDark ? 'bg-gray-800' : 'bg-gray-200'}`}></div>
              </h3>
              <div className="space-y-8">
                {[
                  { title: "Protocol Fees", val: "0.1% - 0.5%", desc: "Applied to every compute job, storage store, or inference." },
                  { title: "Gas Abstraction", val: "5% Premium", desc: "Charged for the convenience of paying in $VAMS while we handle swaps." },
                  { title: "L1 Licensing", val: "B2B", desc: "Enterprise agents paying for dedicated Avalanche L1 setups." }
                ].map((item, i) => (
                  <div key={i} className={`bg-white/10 backdrop-blur-[2px] p-6 border ${borderLight} ${borderHover} transition-colors duration-300 rounded-[9px]`}>
                    <div className="flex justify-between items-baseline mb-2">
                      <h4 className="font-bold text-lg font-serif">{item.title}</h4>
                      <span className={`font-mono text-[10px] ${isDark ? 'bg-black/40' : 'bg-white/40'} px-2 py-1 rounded ${textSub} border border-white/10`}>{item.val}</span>
                    </div>
                    <p className={`text-sm ${textSub} leading-relaxed tracking-wide`}>{item.desc}</p>
                  </div>
                ))}
              </div>
            </div>

            <aside className={`${isDark ? 'bg-white text-black' : 'bg-black text-white'} p-12 relative overflow-hidden shadow-2xl transition-colors duration-700`}>
              <FileText className={`absolute top-6 right-6 ${isDark ? 'text-black/10' : 'text-white/10'} w-24 h-24`} />
              <h3 className="font-serif text-2xl mb-10 relative z-10">Token Distribution</h3>
              <ul className={`space-y-6 font-mono text-sm ${isDark ? 'text-gray-500' : 'text-gray-400'} relative z-10`}>
                {[
                  { l: "Community & Eco", v: "34%" },
                  { l: "Protocol Treasury", v: "21%" },
                  { l: "Founders", v: "16%" },
                  { l: "Investors", v: "14%" },
                  { l: "Team & Advisors", v: "10%" },
                  { l: "Initial Liquidity", v: "5%" },
                ].map((row, idx) => (
                  <li key={idx} className={`flex justify-between border-b ${isDark ? 'border-black/10 hover:text-black' : 'border-white/10 hover:text-white'} pb-2 transition-colors cursor-default`}>
                    <span>{row.l}</span>
                    <span className={isDark ? 'text-black' : 'text-white'}>{row.v}</span>
                  </li>
                ))}
              </ul>
            </aside>
          </div>
        </SectionWrapper>
      </div>

      {/* SECTION 6: ROADMAP */}
      <section id="roadmap" className={`${bgAlt} py-32 border-t ${borderLight} relative transition-colors duration-700`}>
        <div className="max-w-7xl mx-auto px-6 md:px-12 relative z-10">
          <div className="mb-20 flex flex-col md:flex-row justify-between items-end">
            <div>
              <SmokeHeader text="Execution Plan" isDark={isDark} className="font-serif text-5xl block mb-6" />
              <p className={`${textSub} max-w-lg tracking-wide`}>
                From simulation to live testnet. A detailed 24-week MVP execution followed by post-MVP hardening.
              </p>
            </div>
            <div className="mt-8 md:mt-0">
              <MagneticButton ariaLabel="View Full Roadmap" className={`border ${isDark ? 'border-white hover:bg-white hover:text-black' : 'border-black hover:bg-black hover:text-white'} px-6 py-3 font-mono text-xs uppercase transition-colors rounded-[9px]`}>
                View Full Roadmap
              </MagneticButton>
            </div>
          </div>

          <div className="grid md:grid-cols-4 gap-8">
            {[
              { phase: "Phase 1", time: "Weeks 1-8", title: "Foundation", items: ["$VAMS Token Deploy", "Staking Contracts", "Sepolia Testnet"] },
              { phase: "Phase 2", time: "Weeks 9-12", title: "Integration", items: ["Polygon CDK L3", "Unified Liquidity Bridge", "AggLayer Setup"] },
              { phase: "Phase 3", time: "Weeks 13-16", title: "Routing", items: ["CLR Engine Launch", "Avalanche L1 Spin-up", "Cross-chain Gas"] },
              { phase: "Phase 4", time: "Weeks 17-24", title: "Launch", items: ["AWS-Style Console", "First DePIN Integration", "Public Testnet"] },
            ].map((card, i) => (
              <article key={i} className={`${bgMain} p-8 border ${borderLight} hover:-translate-y-2 transition-all duration-500 shadow-sm hover:shadow-xl group`}>
                <div className={`font-mono text-[10px] ${textSub} uppercase mb-4 tracking-widest`}>{card.time}</div>
                <div className="flex items-center gap-3 mb-6">
                  <div className={`w-6 h-6 ${isDark ? 'bg-white text-black group-hover:bg-green-500 group-hover:text-white' : 'bg-black text-white group-hover:bg-green-600'} flex items-center justify-center font-mono text-[10px] rounded-full transition-colors`}>{i + 1}</div>
                  <h3 className="font-serif text-2xl md:text-3xl">{card.title}</h3>
                </div>
                <ul className="space-y-3">
                  {card.items.map((item, j) => (
                    <li key={j} className={`flex items-start gap-2 text-sm ${textSub} tracking-wide`}>
                      <span className={`mt-1.5 w-1 h-1 ${isDark ? 'bg-gray-700 group-hover:bg-white' : 'bg-gray-300 group-hover:bg-black'} rounded-full transition-colors`}></span>
                      {item}
                    </li>
                  ))}
                </ul>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* SECTION 7: TEAM & CONTACT */}
      <SectionWrapper id="contact" className="mb-20">
        <div className="grid md:grid-cols-2 gap-24 items-center">
          <article>
            <span className={`font-mono text-[10px] uppercase ${textSub} tracking-[0.2em] mb-4 block`}>The Team</span>
            <SmokeHeader text="Building in Public" isDark={isDark} className="font-serif text-4xl md:text-6xl mb-8 block" />
            <div className={`flex flex-col md:flex-row items-center md:items-start gap-8 mb-12 border ${borderLight} p-8 shadow-sm ${bgAlt} text-center md:text-left`}>
              <div className={`w-32 h-32 md:w-24 md:h-24 ${isDark ? 'bg-gray-800' : 'bg-gray-100'} rounded-full overflow-hidden flex-shrink-0 border ${borderLight} mx-auto md:mx-0`}>
                <img src={aseemProfile} alt="Aseem Chishti" className="w-full h-full object-cover grayscale hover:grayscale-0 transition-all duration-500" />
              </div>
              <div className="w-full">
                <h3 className="font-serif text-2xl md:text-3xl mb-1">Aseem Chishti</h3>
                <p className={`font-mono text-[10px] uppercase ${textSub} mb-4 tracking-widest`}>Founder & Architect</p>
                <p className={`${textSub} text-sm leading-relaxed font-light tracking-wide mx-auto md:mx-0`}>
                  Sole developer of the 5-Layer VAMS codebase and 6,100+ lines of technical specs. Deep expertise in DePIN, Agentic workflows, and tokenomics.
                </p>
                <div className="flex gap-4 mt-6 justify-center md:justify-start">
                  <a href="https://github.com/GodOfAgents" target="_blank" rel="noopener noreferrer" className={`${textSub} hover:${isDark ? 'text-white' : 'text-black'} transition-colors`} aria-label="GitHub Profile"><Github size={18} /></a>
                  <a href="mailto:aseeminksa@gmail.com" className={`${textSub} hover:${isDark ? 'text-white' : 'text-black'} transition-colors`} aria-label="Email Contact"><Mail size={18} /></a>
                  <a href="https://t.me/AseemChishti" target="_blank" rel="noopener noreferrer" className={`${textSub} hover:${isDark ? 'text-white' : 'text-black'} transition-colors`} aria-label="Telegram"><Send size={18} /></a>
                  <a href="https://www.linkedin.com/in/aseemchishti" target="_blank" rel="noopener noreferrer" className={`${textSub} hover:${isDark ? 'text-white' : 'text-black'} transition-colors`} aria-label="LinkedIn"><Linkedin size={18} /></a>
                  <a href="https://x.com/aseemchishti" target="_blank" rel="noopener noreferrer" className={`${textSub} hover:${isDark ? 'text-white' : 'text-black'} transition-colors`} aria-label="X (Twitter)"><Twitter size={18} /></a>
                </div>
              </div>
            </div>

            <div className={`p-8 ${bgAlt} border ${borderLight} relative overflow-hidden group ${borderHover} transition-colors duration-500`}>
              <div className={`absolute top-0 right-0 w-20 h-20 ${isDark ? 'bg-gray-800 group-hover:bg-white/10' : 'bg-gray-200 group-hover:bg-black/10'} rounded-bl-full -mr-10 -mt-10 transition-all`} aria-hidden="true"></div>
              <h4 className="font-serif text-lg mb-2">Hiring Engineers</h4>
              <p className={`text-sm ${textSub} mb-6 font-light`}>Seeking specialists in Solidity, Rust, and AI/ML Systems.</p>
              <button className={`text-[10px] font-mono uppercase border-b ${isDark ? 'border-white hover:text-gray-300' : 'border-black hover:text-gray-600'} pb-1 tracking-widest rounded-[9px]`}>View Open Roles</button>
            </div>
          </article>

          <aside className="relative">
            <div className={`absolute inset-0 bg-gradient-to-br ${isDark ? 'from-gray-900 to-black' : 'from-gray-100 to-white'} -z-10 transform rotate-2 scale-105 border ${borderLight}`} aria-hidden="true"></div>
            <div className={`${isDark ? 'bg-white text-black' : 'bg-black text-white'} p-12 md:p-16 relative shadow-2xl transition-colors duration-700`}>
              <h3 className="font-serif text-2xl md:text-3xl mb-6">Join the Sovereign Revolution</h3>
              <p className={`${isDark ? 'text-gray-600' : 'text-gray-400'} mb-10 font-light leading-relaxed tracking-wide`}>
                In 5 years, AI Agents will outnumber humans on the internet 100:1. VAMS will be the ground they walk on.
              </p>

              <form className="space-y-8">
                <div className="group">
                  <label className={`block font-mono text-[10px] uppercase ${isDark ? 'text-gray-500 group-focus-within:text-black' : 'text-gray-500 group-focus-within:text-white'} mb-2 tracking-widest transition-colors`}>Email Address</label>
                  <input type="email" className={`w-full bg-transparent border-b ${isDark ? 'border-gray-200' : 'border-gray-800'} py-3 ${isDark ? 'focus:border-black' : 'focus:border-white'} outline-none transition-colors font-serif text-lg`} placeholder="agent@sovereign.ai" />
                </div>
                <div className="group">
                  <label className={`block font-mono text-[10px] uppercase ${isDark ? 'text-gray-500 group-focus-within:text-black' : 'text-gray-500 group-focus-within:text-white'} mb-2 tracking-widest transition-colors`}>Interest</label>
                  <select className={`w-full bg-transparent border-b ${isDark ? 'border-gray-200' : 'border-gray-800'} py-3 ${isDark ? 'focus:border-black' : 'focus:border-white'} outline-none transition-colors ${isDark ? 'text-gray-600' : 'text-gray-400'} font-serif text-lg appearance-none`}>
                    <option>Strategic Partnership</option>
                    <option>Developer Access</option>
                    <option>Investment</option>
                  </select>
                </div>
                <MagneticButton ariaLabel="Submit Access Request" className={`w-full ${isDark ? 'bg-black text-white hover:bg-gray-800' : 'bg-white text-black hover:bg-gray-200'} py-5 font-mono text-xs uppercase tracking-[0.2em] transition-colors mt-8 rounded-[9px]`}>
                  Request Access
                </MagneticButton>
              </form>
            </div>
          </aside>
        </div>
      </SectionWrapper>

      {/* FOOTER */}
      <footer className={`${isDark ? 'bg-black border-gray-900' : 'bg-gray-900 border-gray-800'} text-white py-24 px-6 md:px-12 border-t relative z-10 transition-colors duration-700`}>
        <div className="max-w-7xl mx-auto grid md:grid-cols-4 gap-12 text-sm text-gray-400">
          <div className="col-span-2">
            <div className="flex items-center gap-3 mb-6">
              <img src={vamsLogo} alt="VAMS Protocol" className="w-8 h-8 object-contain" />
            </div>
            <p className="max-w-xs mb-8 font-light leading-relaxed tracking-wide">
              The Verifiable and Agentic Modular Stack.<br />Infrastructure for the next generation of the internet.
            </p>
            <div className="text-[10px] font-mono text-gray-600 uppercase tracking-widest">© 2026 VAMS. ALL RIGHTS RESERVED.</div>
          </div>

          <nav aria-label="Footer Resources">
            <h4 className="text-white font-serif text-lg mb-6">Resources</h4>
            <ul className="space-y-4 font-light">
              <li><a href="https://drive.google.com/file/d/1H6tKKyeqczKr6pmsdqSGdYPrrA4oGr0R/" target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors">Whitepaper</a></li>
              <li><a href="https://github.com/GodOfAgents/VAMS" target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors">Documentation</a></li>
              <li><a href="https://github.com/GodOfAgents/VAMS" target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors">GitHub</a></li>
              <li><a href="#" className="hover:text-white transition-colors">Brand Assets</a></li>
            </ul>
          </nav>

          <nav aria-label="Social Links">
            <h4 className="text-white font-serif text-lg mb-6">Social</h4>
            <ul className="space-y-4 font-light">
              <li><a href="https://x.com/aseemchishti" target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors">Twitter / X</a></li>
              <li><a href="https://discord.gg/Kp2PpXfkV" target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors">Discord</a></li>
              <li><a href="https://t.me/AseemChishti" target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors">Telegram</a></li>
              <li><a href="https://www.linkedin.com/in/aseemchishti" target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors">LinkedIn</a></li>
            </ul>
          </nav>
        </div>
      </footer>
    </main>
  );
}