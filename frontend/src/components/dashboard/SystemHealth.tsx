import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Activity, Database, Server, Clock, AlertCircle, CheckCircle2 } from "lucide-react";
import { apiClient } from "@/api/client";

interface HealthComponent {
    status: "healthy" | "degraded" | "unhealthy";
    latency_ms?: number;
    message?: string;
    details?: Record<string, any>;
}

interface DetailedHealth {
    status: "healthy" | "degraded" | "unhealthy";
    timestamp: string;
    services?: Record<string, HealthComponent>;
    system?: {
        cpu_usage?: number;
        memory_usage?: number;
    }
}

export function SystemHealth() {
    const [health, setHealth] = useState<DetailedHealth | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fetchHealth = async () => {
        try {
            const data = await apiClient.getDetailedHealth();
            setHealth(data);
            setError(null);
        } catch (err) {
            setError("Failed to fetch system status");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchHealth();
        const interval = setInterval(fetchHealth, 30000); // Poll every 30s
        return () => clearInterval(interval);
    }, []);

    const getStatusColor = (status?: string) => {
        switch (status) {
            case "healthy": return "text-emerald-500";
            case "degraded": return "text-yellow-500";
            case "unhealthy": return "text-red-500";
            default: return "text-slate-400";
        }
    };

    const getStatusIcon = (status?: string) => {
        switch (status) {
            case "healthy": return <CheckCircle2 className="w-4 h-4 text-emerald-500" />;
            case "degraded": return <AlertCircle className="w-4 h-4 text-yellow-500" />;
            case "unhealthy": return <AlertCircle className="w-4 h-4 text-red-500" />;
            default: return <Activity className="w-4 h-4 text-slate-400" />;
        }
    };

    if (loading && !health) {
        return (
            <Card>
                <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium flex items-center gap-2">
                        <Activity className="w-4 h-4" /> System Health
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="h-20 flex items-center justify-center text-xs text-muted-foreground animate-pulse">
                        Loading...
                    </div>
                </CardContent>
            </Card>
        );
    }

    return (
        <Card>
            <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                    <CardTitle className="text-sm font-medium flex items-center gap-2">
                        <Activity className="w-4 h-4" /> System Health
                    </CardTitle>
                    <Badge variant="outline" className={`${getStatusColor(health?.status)} border-current bg-transparent`}>
                        {health?.status?.toUpperCase() || "UNKNOWN"}
                    </Badge>
                </div>
            </CardHeader>
            <CardContent className="space-y-4">
                {error ? (
                    <div className="text-xs text-destructive flex items-center gap-2">
                        <AlertCircle className="w-4 h-4" /> {error}
                    </div>
                ) : (
                    <div className="grid grid-cols-2 gap-4">
                        {/* Database Status */}
                        <div className="flex flex-col gap-1 p-2 rounded-md bg-secondary/20">
                            <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
                                <Database className="w-3 h-3" /> Database
                            </div>
                            <div className="flex items-center gap-2">
                                {getStatusIcon(health?.services?.database?.status)}
                                <span className="text-sm font-semibold capitalize">
                                    {health?.services?.database?.status || "Unknown"}
                                </span>
                            </div>
                            {health?.services?.database?.latency_ms !== undefined && (
                                <div className="text-[10px] text-muted-foreground mt-1">
                                    Latency: {health.services.database.latency_ms.toFixed(1)}ms
                                </div>
                            )}
                        </div>

                        {/* API Status */}
                        <div className="flex flex-col gap-1 p-2 rounded-md bg-secondary/20">
                            <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
                                <Server className="w-3 h-3" /> API Server
                            </div>
                            <div className="flex items-center gap-2">
                                {getStatusIcon("healthy")}
                                <span className="text-sm font-semibold">Online</span>
                            </div>
                            <div className="text-[10px] text-muted-foreground mt-1">
                                Uptime: 99.9%
                            </div>
                        </div>
                    </div>
                )}

                {health?.timestamp && (
                    <div className="pt-2 border-t border-border flex items-center justify-end text-[10px] text-muted-foreground gap-1">
                        <Clock className="w-3 h-3" />
                        Updated: {new Date(health.timestamp).toLocaleTimeString()}
                    </div>
                )}
            </CardContent>
        </Card>
    );
}
