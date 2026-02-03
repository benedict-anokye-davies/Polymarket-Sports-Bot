import { useState, useEffect } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { RefreshCw, XCircle, AlertCircle } from "lucide-react";
import { apiClient } from "@/api/client";
import { useToast } from "@/components/ui/use-toast";

interface Order {
    id: string; // Polymarket uses 'id' or 'orderID'
    orderID?: string;
    market: string; // Token ID
    side: "BUY" | "SELL";
    price: string;
    size: string;
    originalSize: string;
    leftSize: string;
    status: string;
    timestamp: number;
}

export function OpenOrders() {
    const [orders, setOrders] = useState<Order[]>([]);
    const [loading, setLoading] = useState(true);
    const [cancelling, setCancelling] = useState<string | null>(null);
    const { toast } = useToast();

    const fetchOrders = async () => {
        try {
            setLoading(true);
            const data = await apiClient.getOpenOrders();
            setOrders(Array.isArray(data) ? data : []);
        } catch (err) {
            console.error("Failed to fetch open orders", err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchOrders();
        const interval = setInterval(fetchOrders, 10000); // Poll every 10s
        return () => clearInterval(interval);
    }, []);

    const handleCancel = async (orderId: string) => {
        try {
            setCancelling(orderId);
            await apiClient.cancelOrder(orderId);
            toast({
                title: "Order Cancelled",
                description: "Your order has been successfully cancelled.",
            });
            fetchOrders(); // Refresh immediately
        } catch (err) {
            toast({
                title: "Cancellation Failed",
                description: "Failed to cancel the order. Please try again.",
                variant: "destructive",
            });
        } finally {
            setCancelling(null);
        }
    };

    const formatPrice = (price: string) => {
        const num = parseFloat(price);
        return isNaN(num) ? price : `$${num.toFixed(2)} (or ${(num * 100).toFixed(1)}¢)`;
    };

    if (loading && orders.length === 0) {
        return (
            <Card>
                <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium">Open Orders</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="text-xs text-muted-foreground animate-pulse">Loading orders...</div>
                </CardContent>
            </Card>
        );
    }

    if (orders.length === 0) {
        return (
            <Card>
                <CardHeader className="pb-2 flex flex-row items-center justify-between">
                    <CardTitle className="text-sm font-medium">Open Orders</CardTitle>
                    <Button variant="ghost" size="icon" onClick={() => fetchOrders()} className="h-6 w-6">
                        <RefreshCw className="h-3 w-3" />
                    </Button>
                </CardHeader>
                <CardContent>
                    <div className="text-xs text-muted-foreground py-4 text-center">
                        No active orders.
                    </div>
                </CardContent>
            </Card>
        )
    }

    return (
        <Card>
            <CardHeader className="pb-2 flex flex-row items-center justify-between">
                <CardTitle className="text-sm font-medium flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 text-primary" /> Open Orders ({orders.length})
                </CardTitle>
                <Button variant="ghost" size="icon" onClick={() => fetchOrders()} className="h-6 w-6">
                    <RefreshCw className="h-3 w-3" />
                </Button>
            </CardHeader>
            <CardContent>
                <div className="overflow-x-auto">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead className="w-[80px]">Side</TableHead>
                                <TableHead>Size</TableHead>
                                <TableHead>Price</TableHead>
                                <TableHead className="text-right">Action</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {orders.map((order) => (
                                <TableRow key={order.id || order.orderID}>
                                    <TableCell>
                                        <Badge variant={order.side === "BUY" ? "default" : "secondary"}>
                                            {order.side}
                                        </Badge>
                                    </TableCell>
                                    <TableCell className="font-mono text-xs">{order.size || order.originalSize}</TableCell>
                                    <TableCell className="font-mono text-xs">{formatPrice(order.price)}</TableCell>
                                    <TableCell className="text-right">
                                        <Button
                                            variant="destructive"
                                            size="sm"
                                            className="h-6 px-2 text-xs"
                                            disabled={cancelling === (order.id || order.orderID)}
                                            onClick={() => handleCancel(order.id || order.orderID!)}
                                        >
                                            {cancelling === (order.id || order.orderID) ? "..." : <XCircle className="w-3 h-3" />}
                                        </Button>
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </div>
            </CardContent>
        </Card>
    );
}
