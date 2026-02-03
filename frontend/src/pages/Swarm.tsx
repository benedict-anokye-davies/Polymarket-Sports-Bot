import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { useQuery } from "@tanstack/react-query";
import { Loader2, Hexagon, Crosshair, TrendingUp, Shield, Activity, RefreshCw } from "lucide-react";
import { Layout } from "@/components/layout/Layout";

interface SwarmMetrics {
    volume: number;
    probability: number;
    pnl?: number;
    last_updated: string;
}

interface SwarmNode {
    id: string;
    ticker: string;
    type: "opportunity" | "position" | "watch";
    status: "active" | "pending" | "cooling";
    coordinates?: { x: number; y: number; z: number };
    metrics: SwarmMetrics;
    platform: string;
}

const HexNode = ({ node, index, total }: { node: SwarmNode; index: number; total: number }) => {
    // Calculate hex position in a spiral/grid
    const angle = (index / total) * Math.PI * 2;
    const radius = node.type === "position" ? 150 : 280; // Positions closer to core
    const x = Math.cos(angle) * radius;
    const y = Math.sin(angle) * radius;

    return (
        <motion.div
            initial={{ opacity: 0, scale: 0, x: 0, y: 0 }}
            animate={{ opacity: 1, scale: 1, x, y }}
            transition={{ type: "spring", stiffness: 100, damping: 20, delay: index * 0.05 }}
            className="absolute flex flex-col items-center justify-center cursor-pointer group"
            style={{ left: "50%", top: "50%" }}
        >
            <div className={`relative flex items-center justify-center w-16 h-16 transition-all duration-300 group-hover:scale-110 ${node.type === "position" ? "text-emerald-400 drop-shadow-[0_0_8px_rgba(52,211,153,0.5)]" :
                    node.type === "opportunity" ? "text-blue-400 drop-shadow-[0_0_8px_rgba(96,165,250,0.5)]" : "text-slate-500"
                }`}>
                <Hexagon className="w-full h-full fill-background/80 stroke-[1.5]" />

                {/* Inner Icon */}
                <div className="absolute inset-0 flex items-center justify-center">
                    {node.type === "position" ? <Shield className="w-6 h-6" /> : <Crosshair className="w-6 h-6" />}
                </div>

                {/* Status Ring */}
                <svg className="absolute w-20 h-20 -rotate-90 pointer-events-none">
                    <circle
                        cx="40"
                        cy="40"
                        r="38"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1"
                        strokeDasharray="240"
                        strokeDashoffset={240 - (node.metrics.probability / 100) * 240}
                        className="opacity-50"
                    />
                </svg>
            </div>

            {/* Label Tooltip (Always visible on hover, or static if needed) */}
            <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="absolute mt-20 px-3 py-1 bg-black/80 backdrop-blur-md border border-white/10 rounded-full text-xs font-mono whitespace-nowrap z-10"
            >
                <span className={node.metrics.pnl && node.metrics.pnl > 0 ? "text-green-400" : "text-white"}>
                    {node.ticker}
                </span>
                {node.metrics.pnl && (
                    <span className="ml-2 opacity-70">${node.metrics.pnl.toFixed(2)}</span>
                )}
            </motion.div>
        </motion.div>
    );
};

const CoreHUD = () => (
    <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-32 h-32 rounded-full border border-white/10 bg-black/40 backdrop-blur-xl flex flex-col items-center justify-center z-0">
        <div className="absolute inset-0 rounded-full border-t border-emerald-500/50 animate-spin-slow" />
        <div className="absolute inset-2 rounded-full border-b border-blue-500/30 animate-spin-reverse-slower" />
        <Activity className="w-8 h-8 text-white/80" />
        <span className="text-[10px] font-mono text-white/50 mt-1">SYSTEM ONLINE</span>
    </div>
);

export default function Swarm() {
    const { data: nodes, isLoading, refetch } = useQuery<SwarmNode[]>({
        queryKey: ["swarm-state"],
        queryFn: async () => {
            const res = await api.get("/swarm/state");
            return res.data;
        },
        refetchInterval: 5000,
    });

    return (
        <Layout>
            <div className="relative h-[calc(100vh-4rem)] w-full overflow-hidden bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 flex items-center justify-center">

                {/* Background Grid */}
                <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.03)_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_60%_60%_at_50%_50%,black,transport)] pointer-events-none" />

                {/* Header Overlay */}
                <div className="absolute top-6 left-6 z-20">
                    <h1 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-slate-500 font-mono tracking-tight">
                        STRATEGY SWARM
                    </h1>
                    <p className="text-sm text-slate-400 font-mono flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                        LIVE FEED
                    </p>
                </div>

                {/* Controls */}
                <div className="absolute top-6 right-6 z-20 flex gap-2">
                    <button onClick={() => refetch()} className="p-2 rounded-full bg-white/5 hover:bg-white/10 border border-white/5 transition-colors">
                        <RefreshCw className={`w-4 h-4 text-white/70 ${isLoading ? 'animate-spin' : ''}`} />
                    </button>
                </div>

                {/* Main Visualization Area */}
                <div className="relative w-full h-full max-w-5xl max-h-[800px]">
                    {isLoading && !nodes ? (
                        <div className="absolute inset-0 flex items-center justify-center">
                            <Loader2 className="w-8 h-8 text-emerald-500 animate-spin" />
                        </div>
                    ) : (
                        <div className="relative w-full h-full">
                            <CoreHUD />
                            <AnimatePresence>
                                {nodes?.map((node, i) => (
                                    <HexNode key={node.id} node={node} index={i} total={nodes.length} />
                                ))}
                            </AnimatePresence>
                        </div>
                    )}
                </div>

            </div>
        </Layout>
    );
}
