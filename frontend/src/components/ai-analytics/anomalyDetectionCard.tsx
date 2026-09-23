"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AlertTriangle, Shield, Eye } from "lucide-react";
import { motion } from "framer-motion";
import { Badge } from "@/components/ui/badge";
import { useEffect, useState } from "react";
import { aiAnalyticsApi } from "@/lib/api/client";

const cardVariants = {
	hidden: { opacity: 0, y: 20 },
	visible: {
		opacity: 1,
		y: 0,
		transition: {
			duration: 0.5,
			ease: "easeOut" as const,
			delay: 0.3,
		},
	},
};

const getSeverityColor = (severity: string) => {
	switch (severity) {
		case "high":
			return "border-rose-400/30 bg-rose-500/15 text-rose-300";
		case "medium":
			return "border-amber-400/30 bg-amber-500/15 text-amber-300";
		case "low":
			return "border-primary/30 bg-primary/15 text-primary";
		default:
			return "border-border bg-muted text-muted-foreground";
	}
};

const getSeverityIcon = (severity: string) => {
	switch (severity) {
		case "high":
			return <AlertTriangle className="w-3 h-3 mr-1" />;
		case "medium":
			return <Eye className="w-3 h-3 mr-1" />;
		case "low":
			return <Shield className="w-3 h-3 mr-1" />;
		default:
			return null;
	}
};

export default function AnomalyDetectionCard() {
	const [anomalies, setAnomalies] = useState<any[]>([]);
	const [isLoading, setIsLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		const fetchAnomalies = async () => {
			try {
				setError(null);
				const response = await aiAnalyticsApi.getAnomalies();
				if (response.success) {
					setAnomalies(response.anomalies || []);
				} else {
					setError("Could not load anomalies.");
				}
			} catch (err) {
				console.error("Failed to fetch anomalies:", err);
				setError("Could not load anomalies.");
			} finally {
				setIsLoading(false);
			}
		};

		fetchAnomalies();
	}, []);

	const highRiskCount = anomalies.filter(
		(a) => a.risk_level === "HIGH"
	).length;

	return (
		<motion.div
			variants={cardVariants}
			initial="hidden"
			animate="visible"
			className="h-full"
		>
			<Card className="flex h-full flex-col border-border/70 bg-card/80 shadow-lg shadow-black/10 transition-all duration-300 hover:shadow-xl hover:shadow-black/10">
				<CardHeader className="pb-3">
					<CardTitle className="flex items-center justify-between text-lg font-semibold text-foreground">
						<div className="flex items-center gap-2">
							<AlertTriangle className="h-5 w-5 text-rose-300" />
							Anomaly Detection
						</div>
						<Badge
							variant="outline"
							className="border-rose-400/30 bg-rose-500/10 text-rose-300"
						>
							{highRiskCount} High
						</Badge>
					</CardTitle>
				</CardHeader>
				<CardContent className="flex-1 overflow-hidden">
					{isLoading ? (
						<div className="animate-pulse space-y-3">
							<div className="h-20 rounded bg-muted"></div>
							<div className="h-20 rounded bg-muted"></div>
						</div>
					) : error ? (
						<div className="py-8 text-center text-muted-foreground">
							{error}
						</div>
					) : anomalies.length === 0 ? (
						<div className="py-8 text-center text-muted-foreground">
							No anomalies detected
						</div>
					) : (
						<div className="space-y-3 h-[200px] overflow-y-auto pr-2 custom-scrollbar">
							{anomalies.map((anomaly, index) => (
								<motion.div
									key={anomaly.id}
									initial={{ opacity: 0, x: -20 }}
									animate={{ opacity: 1, x: 0 }}
									transition={{
										duration: 0.3,
										delay: anomaly.id * 0.1,
									}}
									className="cursor-pointer rounded-xl border-l-4 bg-background/60 p-4 transition-all duration-200 hover:bg-accent/60 hover:shadow-md"
									style={{
										borderLeftColor:
											anomaly.risk_level === "HIGH"
												? "#ef4444"
												: anomaly.risk_level ===
												  "MEDIUM"
												? "#f59e0b"
												: "#3b82f6",
									}}
								>
									<div className="flex items-start justify-between mb-2">
										<div className="flex-1">
											<div className="flex items-center gap-2 mb-1">
												<h4 className="text-sm font-semibold text-foreground">
													{anomaly.vendor_name}
												</h4>
												<Badge
													variant="outline"
													className={`text-xs ${getSeverityColor(
														anomaly.risk_level?.toLowerCase() ||
															"low"
													)}`}
												>
													{getSeverityIcon(
														anomaly.risk_level?.toLowerCase() ||
															"low"
													)}
													{anomaly.risk_level ||
														"LOW"}
												</Badge>
											</div>
											<p className="text-xs text-muted-foreground">
												{anomaly.date}
											</p>
										</div>
										<div className="text-right">
											<p className="font-bold text-foreground">
												₹{anomaly.amount.toFixed(2)}
											</p>
										</div>
									</div>
									<p className="mb-2 text-sm text-muted-foreground">
										{anomaly.description}
									</p>
									<div className="mt-2 flex items-center gap-1 rounded-lg border border-border/70 bg-card/70 p-2">
										<Shield className="h-3 w-3 text-muted-foreground" />
										<p className="text-xs italic text-muted-foreground">
											{anomaly.explanation ||
												"Anomaly detected"}
										</p>
									</div>
								</motion.div>
							))}
						</div>
					)}
				</CardContent>
			</Card>
		</motion.div>
	);
}
