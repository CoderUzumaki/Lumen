"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
	Lightbulb,
	TrendingDown,
	Repeat,
	DollarSign,
	CheckCircle,
} from "lucide-react";
import { motion } from "framer-motion";
import { Badge } from "@/components/ui/badge";

// Mock data - Replace with API call
const mockSuggestions = [
	{
		id: 1,
		type: "cost-saving",
		title: "Consolidate Cloud Subscriptions",
		description:
			"You have 3 separate cloud storage subscriptions (Dropbox, Google Drive, OneDrive) totaling €89/month. Consolidating to a single Business plan could save €35/month.",
		potentialSaving: 420,
		impact: "high",
		icon: DollarSign,
	},
	{
		id: 2,
		type: "duplicate",
		title: "Remove Duplicate Software Licenses",
		description:
			"Detected duplicate Zoom subscriptions (Pro + Business). The Business plan includes all Pro features. Cancel Pro to save €149/month.",
		potentialSaving: 1788,
		impact: "high",
		icon: Repeat,
	},
	{
		id: 3,
		type: "optimization",
		title: "Optimize Office Supplies Ordering",
		description:
			"Your office supplies orders show high frequency with low volume. Switching to monthly bulk orders could reduce costs by 15% through volume discounts.",
		potentialSaving: 480,
		impact: "medium",
		icon: TrendingDown,
	},
	{
		id: 4,
		type: "opportunity",
		title: "Early Payment Discount Opportunity",
		description:
			"3 vendors offer 2% early payment discounts. Based on your cash flow, you could save €245 annually by paying invoices 10 days early.",
		potentialSaving: 245,
		impact: "low",
		icon: CheckCircle,
	},
	{
		id: 5,
		type: "cost-saving",
		title: "Renegotiate Software Renewal",
		description:
			"Your Salesforce license renews in 30 days. Historical data shows similar businesses negotiate 12-18% discounts at renewal. Estimated savings: €2,160/year.",
		potentialSaving: 2160,
		impact: "high",
		icon: DollarSign,
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
			delay: 0.4,
		},
	},
};

const getImpactColor = (impact: string) => {
	switch (impact) {
		case "high":
			return "bg-green-900/50 text-green-300 border-green-700";
		case "medium":
			return "bg-yellow-900/50 text-yellow-300 border-yellow-700";
		case "low":
			return "bg-blue-900/50 text-blue-300 border-blue-700";
		default:
			return "bg-slate-700 text-slate-300 border-slate-600";
	}
};

export default function AISuggestionsCard() {
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
							<Lightbulb className="w-5 h-5 text-yellow-400" />
							AI Suggestions
						</div>
						<Badge
							variant="outline"
							className="bg-green-900/30 text-green-300 border-green-700"
						>
							Save €5,093/year
						</Badge>
					</CardTitle>
				</CardHeader>
				<CardContent className="flex-1 overflow-hidden">
					<div className="space-y-3 h-[200px] overflow-y-auto pr-2 custom-scrollbar">
						{mockSuggestions.map((suggestion) => {
							const Icon = suggestion.icon;
							return (
								<motion.div
									key={suggestion.id}
									initial={{ opacity: 0, x: -20 }}
									animate={{ opacity: 1, x: 0 }}
									transition={{
										duration: 0.3,
										delay: suggestion.id * 0.1,
									}}
									className="p-4 rounded-lg bg-gradient-to-br from-slate-700/50 to-slate-800/50 border border-slate-600 hover:shadow-md transition-all duration-200 cursor-pointer group"
								>
									<div className="flex items-start gap-3 mb-2">
										<div className="p-2 bg-yellow-900/30 rounded-lg group-hover:bg-yellow-900/50 transition-colors">
											<Icon className="w-4 h-4 text-yellow-400" />
										</div>
										<div className="flex-1">
											<div className="flex items-start justify-between mb-1">
												<h4 className="font-semibold text-white text-sm">
													{suggestion.title}
												</h4>
												<Badge
													variant="outline"
													className={`text-xs ml-2 ${getImpactColor(
														suggestion.impact
													)}`}
												>
													{suggestion.impact}
												</Badge>
											</div>
											<p className="text-xs text-slate-300 leading-relaxed">
												{suggestion.description}
											</p>
										</div>
									</div>
									<div className="flex items-center justify-between mt-3 pt-3 border-t border-slate-600">
										<p className="text-xs text-slate-400">
											Potential Annual Savings
										</p>
										<p className="font-bold text-green-600">
											€
											{suggestion.potentialSaving.toLocaleString()}
										</p>
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
