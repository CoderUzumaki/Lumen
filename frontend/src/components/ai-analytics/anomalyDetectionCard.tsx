"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AlertTriangle, Shield, Eye } from "lucide-react";
import { motion } from "framer-motion";
import { Badge } from "@/components/ui/badge";

// Mock data - Replace with API call
const mockAnomalies = [
	{
		id: 1,
		severity: "high",
		vendor: "Tech Solutions Ltd",
		amount: 8500.0,
		date: "Nov 12, 2025",
		description: "Invoice amount 350% higher than usual monthly average",
		reason: "Unusual spike in transaction value",
	},
	{
		id: 2,
		severity: "medium",
		vendor: "Office Depot",
		amount: 450.0,
		date: "Nov 10, 2025",
		description: "Duplicate transaction detected within 24 hours",
		reason: "Potential duplicate charge",
	},
	{
		id: 3,
		severity: "low",
		vendor: "Cloud Storage Pro",
		amount: 99.99,
		date: "Nov 08, 2025",
		description: "Payment made to new vendor for the first time",
		reason: "New vendor alert",
	},
	{
		id: 4,
		severity: "high",
		vendor: "Unknown Supplier",
		amount: 1200.0,
		date: "Nov 14, 2025",
		description: "Transaction from unregistered vendor",
		reason: "Vendor not in approved list",
	},
];

const cardVariants = {
	hidden: { opacity: 0, y: 20 },
	visible: {
		opacity: 1,
		y: 0,
		transition: {
			duration: 0.5,
			ease: "easeOut",
			delay: 0.3,
		},
	},
};

const getSeverityColor = (severity: string) => {
	switch (severity) {
		case "high":
			return "bg-red-900/50 text-red-300 border-red-700";
		case "medium":
			return "bg-yellow-900/50 text-yellow-300 border-yellow-700";
		case "low":
			return "bg-blue-900/50 text-blue-300 border-blue-700";
		default:
			return "bg-slate-700 text-slate-300 border-slate-600";
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
							{
								mockAnomalies.filter(
									(a) => a.severity === "high"
								).length
							}{" "}
							High
						</Badge>
					</CardTitle>
				</CardHeader>
				<CardContent className="flex-1 overflow-hidden">
					<div className="space-y-3 h-[200px] overflow-y-auto pr-2 custom-scrollbar">
						{mockAnomalies.map((anomaly) => (
							<motion.div
								key={anomaly.id}
								initial={{ opacity: 0, x: -20 }}
								animate={{ opacity: 1, x: 0 }}
								transition={{
									duration: 0.3,
									delay: anomaly.id * 0.1,
								}}
								className="p-4 rounded-lg border-l-4 bg-slate-700/50 border-slate-300 hover:bg-slate-700/70 transition-all duration-200 hover:shadow-md cursor-pointer"
								style={{
									borderLeftColor:
										anomaly.severity === "high"
											? "#ef4444"
											: anomaly.severity === "medium"
											? "#f59e0b"
											: "#3b82f6",
								}}
							>
								<div className="flex items-start justify-between mb-2">
									<div className="flex-1">
										<div className="flex items-center gap-2 mb-1">
											<h4 className="font-semibold text-white text-sm">
												{anomaly.vendor}
											</h4>
											<Badge
												variant="outline"
												className={`text-xs ${getSeverityColor(
													anomaly.severity
												)}`}
											>
												{getSeverityIcon(
													anomaly.severity
												)}
												{anomaly.severity.toUpperCase()}
											</Badge>
										</div>
										<p className="text-xs text-slate-300">
											{anomaly.date}
										</p>
									</div>
									<div className="text-right">
										<p className="font-bold text-white">
											€{anomaly.amount.toFixed(2)}
										</p>
									</div>
								</div>
								<p className="text-sm text-slate-200 mb-2">
									{anomaly.description}
								</p>
								<div className="flex items-center gap-1 mt-2 p-2 bg-slate-800/50 rounded border border-slate-600">
									<Shield className="w-3 h-3 text-slate-400" />
									<p className="text-xs text-slate-300 italic">
										{anomaly.reason}
									</p>
								</div>
							</motion.div>
						))}
					</div>
				</CardContent>
			</Card>
		</motion.div>
	);
}
