import HeroSection from "@/components/landing/HeroSection";
import ProblemSolutionSection from "@/components/landing/ProblemSolutionSection";
import TransparencyHub from "@/components/landing/TransparencyHub";
import WhyVAMSWinsSection from "@/components/landing/WhyVAMSWinsSection";
import LiveStatusDashboard from "@/components/landing/LiveStatusDashboard";
import TechStackExplainer from "@/components/landing/TechStackExplainer";
import TechnicalMoatSection from "@/components/landing/TechnicalMoatSection";
import RoadmapTimeline from "@/components/landing/RoadmapTimeline";
import Vision2030Section from "@/components/landing/Vision2030Section";

export default function Home() {
  return (
    <main className="min-h-screen bg-[var(--background)] selection:bg-cyan-500/30">
      <HeroSection />
      <ProblemSolutionSection />
      <TransparencyHub />
      <WhyVAMSWinsSection />
      <LiveStatusDashboard />
      <TechStackExplainer />
      <TechnicalMoatSection />
      <RoadmapTimeline />
      <Vision2030Section />

      {/* Simple Footer */}
      <footer className="py-12 border-t border-white/5 text-center text-gray-500 text-sm bg-black">
        <div className="max-w-7xl mx-auto px-4">
          <p>© 2026 VAMS Project. All rights reserved.</p>
          <p className="mt-2 text-xs opacity-60">&quot;Code is Law. Verify Everything.&quot;</p>
        </div>
      </footer>
    </main>
  );
}
