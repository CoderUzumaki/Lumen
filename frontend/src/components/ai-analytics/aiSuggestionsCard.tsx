"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
	Lightbulb,
	TrendingDown,
	Repeat,
	DollarSign,
	CheckCircle,
	AlertTriangle,
	Target,
	Zap,
} from "lucide-react";
import { motion } from "framer-motion";
import { Badge } from "@/components/ui/badge";
import { useState, useEffect } from "react";
import { aiAnalyticsApi } from "@/lib/api/client";

const iconMap: { [key: string]: any } = {
	"cost-saving": DollarSign,
	duplicate: Repeat,
	optimization: TrendingDown,
	opportunity: CheckCircle,
	warning: AlertTriangle,
	recommendation: Target,
	insight: Lightbulb,
	action: Zap,
};

const cardVariants = {
	hidden: { opacity: 0, y: 20 },
	visible: {
		opacity: 1,
		y: 0,
		transition: {
			duration: 0.5,
			ease: [0.4, 0, 0.2, 1] as any,
			delay: 0.4,
		},
	},
};

const getImpactColor = (severity: string) => {
	switch (severity?.toLowerCase()) {
		case "critical":
		case "high":
			return "bg-red-100 text-red-700 border-red-300";
		case "medium":
			return "bg-yellow-100 text-yellow-700 border-yellow-300";
		case "low":
		case "info":
			return "bg-blue-100 text-blue-700 border-blue-300";
		default:
			return "bg-gray-100 text-gray-700 border-gray-300";
	}
};

export default function AISuggestionsCard() {
	const [suggestions, setSuggestions] = useState<any[]>([]);
	const [loading, setLoading] = useState(true);

	useEffect(() => {
		const fetchSuggestions = async () => {
			try {
				const response = await aiAnalyticsApi.getInsights({
					userId: "123",
					limit: 10,
				});
				if (response.success && response.insights) {
					setSuggestions(response.insights);
				} else {
					setSuggestions([]);
				}
			} catch (err) {
				console.error("Failed to load AI suggestions", err);
				setSuggestions([]);
			} finally {
				setLoading(false);
			}
		};
		fetchSuggestions();
	}, []);

	if (loading) {
		return (
			<Card className="bg-white border border-gray-200 shadow-sm h-full">
				<CardContent className="flex items-center justify-center h-[300px]">
					<p className="text-gray-500">Loading AI suggestions...</p>
				</CardContent>
			</Card>
		);
	}

	if (suggestions.length === 0) {
		return (
			<Card className="bg-white border border-gray-200 shadow-sm h-full">
				<CardContent className="flex items-center justify-center h-[300px]">
					<div className="text-center">
						<Lightbulb className="w-12 h-12 text-gray-400 mx-auto mb-3" />
						<p className="text-gray-500">
							No suggestions available yet
						</p>
						<p className="text-sm text-gray-400 mt-1">
							AI analysis will generate insights based on your
							transaction data
						</p>
					</div>
				</CardContent>
			</Card>
		);
	}

	return (
		<motion.div
			variants={cardVariants}
			initial="hidden"
			animate="visible"
			className="h-full"
		>
			<Card className="bg-white border border-gray-200 shadow-sm hover:shadow-md transition-all duration-300 h-full flex flex-col">
				<CardHeader className="pb-3">
					<CardTitle className="text-lg font-semibold text-gray-900 flex items-center justify-between">
						<div className="flex items-center gap-2">
							<Lightbulb className="w-5 h-5 text-yellow-600" />
							AI Suggestions
						</div>
						<Badge
							variant="outline"
							className="bg-blue-50 text-blue-700 border-blue-300"
						>
							{suggestions.length} insights
						</Badge>
					</CardTitle>
				</CardHeader>
				<CardContent className="flex-1 overflow-hidden">
					<div className="space-y-3 h-[200px] overflow-y-auto pr-2 custom-scrollbar">
						{suggestions.map((suggestion, index) => {
							const Icon =
								iconMap[suggestion.insight_type] || Lightbulb;
							return (
								<motion.div
									key={suggestion.id}
									initial={{ opacity: 0, x: -20 }}
									animate={{ opacity: 1, x: 0 }}
									transition={{
										duration: 0.3,
										delay: index * 0.1,
									}}
									className="p-4 rounded-lg bg-gray-50 border border-gray-200 hover:shadow-md transition-all duration-200 cursor-pointer group"
								>
									<div className="flex items-start gap-3 mb-2">
										<div className="p-2 bg-yellow-100 rounded-lg group-hover:bg-yellow-200 transition-colors">
											<Icon className="w-4 h-4 text-yellow-600" />
										</div>
										<div className="flex-1">
											<div className="flex items-start justify-between mb-1">
												<h4 className="font-semibold text-gray-900 text-sm">
													{suggestion.title}
												</h4>
												{suggestion.severity && (
													<Badge
														variant="outline"
														className={`text-xs ml-2 ${getImpactColor(
															suggestion.severity
														)}`}
													>
														{suggestion.severity}
													</Badge>
												)}
											</div>
											<p className="text-xs text-gray-600 leading-relaxed">
												{suggestion.description}
											</p>
											{suggestion.confidence_score && (
												<div className="mt-2 flex items-center gap-1">
													<div className="h-1 flex-1 bg-gray-200 rounded-full overflow-hidden">
														<div
															className="h-full bg-blue-500 rounded-full"
															style={{
																width: `${
																	suggestion.confidence_score *
																	100
																}%`,
															}}
														/>
													</div>
													<span className="text-xs text-gray-500">
														{(
															suggestion.confidence_score *
															100
														).toFixed(0)}
														%
													</span>
												</div>
											)}
										</div>
									</div>
								</motion.div>
							);
						})}
					</div>
				</CardContent>
			</Card>
		</motion.div>
	);
}
