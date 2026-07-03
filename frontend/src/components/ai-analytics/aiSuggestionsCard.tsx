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
			return "border-rose-400/30 bg-rose-500/15 text-rose-300";
		case "medium":
			return "border-amber-400/30 bg-amber-500/15 text-amber-300";
		case "low":
		case "info":
			return "border-primary/30 bg-primary/15 text-primary";
		default:
			return "border-border bg-muted text-muted-foreground";
	}
};

export default function AISuggestionsCard() {
	const [suggestions, setSuggestions] = useState<any[]>([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		const fetchSuggestions = async () => {
			try {
				setError(null);
				const response = await aiAnalyticsApi.getInsights({
					limit: 10,
				});
				if (response.success && response.insights) {
					setSuggestions(response.insights);
				} else {
					setError("Could not load AI suggestions.");
					setSuggestions([]);
				}
			} catch (err) {
				console.error("Failed to load AI suggestions", err);
				setError("Could not load AI suggestions.");
				setSuggestions([]);
			} finally {
				setLoading(false);
			}
		};
		fetchSuggestions();
	}, []);

	if (loading) {
		return (
			<Card className="h-full border-border/70 bg-card/80 shadow-lg shadow-black/10">
				<CardContent className="flex items-center justify-center h-[300px]">
					<p className="text-muted-foreground">Loading AI suggestions...</p>
				</CardContent>
			</Card>
		);
	}

	if (error) {
		return (
			<Card className="h-full border-border/70 bg-card/80 shadow-lg shadow-black/10">
				<CardContent className="flex items-center justify-center h-[300px]">
					<p className="text-muted-foreground">{error}</p>
				</CardContent>
			</Card>
		);
	}

	if (suggestions.length === 0) {
		return (
			<Card className="h-full border-border/70 bg-card/80 shadow-lg shadow-black/10">
				<CardContent className="flex items-center justify-center h-[300px]">
					<div className="text-center">
						<Lightbulb className="mx-auto mb-3 h-12 w-12 text-muted-foreground" />
						<p className="text-muted-foreground">
							No suggestions available yet
						</p>
						<p className="mt-1 text-sm text-muted-foreground">
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
			<Card className="flex h-full flex-col border-border/70 bg-card/80 shadow-lg shadow-black/10 transition-all duration-300 hover:shadow-xl hover:shadow-black/10">
				<CardHeader className="pb-3">
					<CardTitle className="flex items-center justify-between text-lg font-semibold text-foreground">
						<div className="flex items-center gap-2">
							<Lightbulb className="h-5 w-5 text-amber-300" />
							AI Suggestions
						</div>
						<Badge
							variant="outline"
							className="border-primary/30 bg-primary/10 text-primary"
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
									className="group cursor-pointer rounded-xl border border-border/70 bg-background/55 p-4 transition-all duration-200 hover:bg-accent/60 hover:shadow-md"
								>
									<div className="flex items-start gap-3 mb-2">
										<div className="rounded-lg bg-amber-500/15 p-2 transition-colors group-hover:bg-amber-500/20">
											<Icon className="h-4 w-4 text-amber-300" />
										</div>
										<div className="flex-1">
											<div className="flex items-start justify-between mb-1">
												<h4 className="text-sm font-semibold text-foreground">
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
											<p className="text-xs leading-relaxed text-muted-foreground">
												{suggestion.description}
											</p>
											{suggestion.confidence_score && (
												<div className="mt-2 flex items-center gap-1">
													<div className="h-1 flex-1 overflow-hidden rounded-full bg-muted">
														<div
															className="h-full rounded-full bg-primary"
															style={{
																width: `${
																	suggestion.confidence_score *
																	100
																}%`,
															}}
														/>
													</div>
													<span className="text-xs text-muted-foreground">
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
