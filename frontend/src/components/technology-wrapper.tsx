"use client";

import dynamic from "next/dynamic";

const TechnologyContent = dynamic(() => import("./technology").then(mod => mod.Technology), {
    ssr: false,
});

export function TechnologyWrapper() {
    return <TechnologyContent />;
}
