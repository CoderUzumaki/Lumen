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
			return "bg-red-100 text-red-700 border-red-300";
		case "medium":
			return "bg-yellow-100 text-yellow-700 border-yellow-300";
		case "low":
			return "bg-blue-100 text-blue-700 border-blue-300";
		default:
			return "bg-gray-100 text-gray-700 border-gray-300";
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

	useEffect(() => {
		const fetchAnomalies = async () => {
			try {
				const response = await aiAnalyticsApi.getAnomalies("123");
				if (response.success) {
					setAnomalies(response.anomalies || []);
				}
			} catch (error) {
				console.error("Failed to fetch anomalies:", error);
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
			<Card className="border-slate-800 shadow-lg hover:shadow-xl transition-all duration-300 bg-slate-900/50 backdrop-blur-sm h-full flex flex-col">
				<CardHeader className="pb-3">
					<CardTitle className="text-lg font-semibold text-white flex items-center justify-between">
						<div className="flex items-center gap-2">
							<AlertTriangle className="w-5 h-5 text-red-400" />
							Anomaly Detection
						</div>
						<Badge
							variant="outline"
							className="bg-red-900/30 text-red-300 border-red-700"
						>
							{highRiskCount} High
						</Badge>
					</CardTitle>
				</CardHeader>
				<CardContent className="flex-1 overflow-hidden">
					{isLoading ? (
						<div className="animate-pulse space-y-3">
							<div className="h-20 bg-slate-700 rounded"></div>
							<div className="h-20 bg-slate-700 rounded"></div>
						</div>
					) : anomalies.length === 0 ? (
						<div className="text-center py-8 text-slate-400">
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
									className="p-4 rounded-lg border-l-4 bg-gray-50 border-gray-300 hover:bg-gray-100 transition-all duration-200 hover:shadow-md cursor-pointer"
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
												<h4 className="font-semibold text-gray-900 text-sm">
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
											<p className="text-xs text-gray-600">
												{anomaly.date}
											</p>
										</div>
										<div className="text-right">
											<p className="font-bold text-gray-900">
												€{anomaly.amount.toFixed(2)}
											</p>
										</div>
									</div>
									<p className="text-sm text-gray-700 mb-2">
										{anomaly.description}
									</p>
									<div className="flex items-center gap-1 mt-2 p-2 bg-gray-100 rounded border border-gray-200">
										<Shield className="w-3 h-3 text-gray-600" />
										<p className="text-xs text-gray-600 italic">
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
