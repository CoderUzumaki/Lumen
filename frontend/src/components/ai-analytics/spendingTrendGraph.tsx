"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TrendingUp, Activity } from "lucide-react";
import { motion } from "framer-motion";
import {
	LineChart,
	Line,
	XAxis,
	YAxis,
	CartesianGrid,
	Tooltip,
	ResponsiveContainer,
	Legend,
} from "recharts";

// Mock data - Replace with API call
const mockSpendingData = [
	{ month: "Jan", spending: 18500, forecast: 18000, budget: 20000 },
	{ month: "Feb", spending: 19200, forecast: 19000, budget: 20000 },
	{ month: "Mar", spending: 17800, forecast: 18500, budget: 20000 },
	{ month: "Apr", spending: 21500, forecast: 19000, budget: 20000 },
	{ month: "May", spending: 19800, forecast: 20000, budget: 20000 },
	{ month: "Jun", spending: 20500, forecast: 20500, budget: 20000 },
	{ month: "Jul", spending: 22100, forecast: 21000, budget: 20000 },
	{ month: "Aug", spending: 19500, forecast: 20000, budget: 20000 },
	{ month: "Sep", spending: 20800, forecast: 20500, budget: 20000 },
	{ month: "Oct", spending: 21200, forecast: 21000, budget: 20000 },
	{ month: "Nov", spending: 18200, forecast: 19500, budget: 20000 },
	{ month: "Dec", spending: null, forecast: 20000, budget: 20000 },
];

const cardVariants = {
	hidden: { opacity: 0, y: 20 },
	visible: {
		opacity: 1,
		y: 0,
		transition: {
			duration: 0.5,
			ease: "easeOut",
			delay: 0.5,
		},
	},
};

const CustomTooltip = ({ active, payload, label }: any) => {
	if (active && payload && payload.length) {
		return (
			<div className="bg-slate-800 p-3 border border-slate-600 rounded-lg shadow-lg">
				<p className="font-semibold text-white mb-2">{label}</p>
				{payload.map((entry: any, index: number) => (
					<p
						key={index}
						className="text-sm"
						style={{ color: entry.color }}
					>
						{entry.name}: €{entry.value?.toLocaleString()}
					</p>
				))}
			</div>
		);
	}
	return null;
};

export default function SpendingTrendGraph() {
	return (
		<motion.div
			variants={cardVariants}
			initial="hidden"
			animate="visible"
			className="h-full"
		>
			<Card className="border-slate-800 shadow-lg hover:shadow-xl transition-all duration-300 bg-slate-900/50 backdrop-blur-sm h-full">
				<CardHeader className="pb-3">
					<CardTitle className="text-lg font-semibold text-white flex items-center justify-between">
						<div className="flex items-center gap-2">
							<Activity className="w-5 h-5 text-indigo-400" />
							Spending Trends
						</div>
						<div className="flex items-center gap-2 text-sm">
							<div className="flex items-center gap-1">
								<div className="w-3 h-3 bg-indigo-400 rounded-full"></div>
								<span className="text-xs text-slate-300">
									Actual
								</span>
							</div>
							<div className="flex items-center gap-1">
								<div className="w-3 h-3 bg-orange-500 rounded-full"></div>
								<span className="text-xs text-slate-300">
									Forecast
								</span>
							</div>
							<div className="flex items-center gap-1">
								<div className="w-3 h-3 bg-slate-500 rounded-full"></div>
								<span className="text-xs text-slate-300">
									Budget
								</span>
							</div>
						</div>
					</CardTitle>
				</CardHeader>
				<CardContent>
					<div className="h-[300px] w-full">
						<ResponsiveContainer width="100%" height="100%">
							<LineChart
								data={mockSpendingData}
								margin={{
									top: 5,
									right: 20,
									left: 10,
									bottom: 5,
								}}
							>
								<CartesianGrid
									strokeDasharray="3 3"
									stroke="#334155"
								/>
								<XAxis
									dataKey="month"
									stroke="#94a3b8"
									style={{ fontSize: "12px" }}
								/>
								<YAxis
									stroke="#94a3b8"
									style={{ fontSize: "12px" }}
									tickFormatter={(value) =>
										`€${value / 1000}k`
									}
								/>
								<Tooltip content={<CustomTooltip />} />
								<Line
									type="monotone"
									dataKey="spending"
									stroke="#818cf8"
									strokeWidth={3}
									dot={{ fill: "#818cf8", r: 4 }}
									activeDot={{ r: 6 }}
									name="Actual Spending"
								/>
								<Line
									type="monotone"
									dataKey="forecast"
									stroke="#f97316"
									strokeWidth={2}
									strokeDasharray="5 5"
									dot={{ fill: "#f97316", r: 3 }}
									name="AI Forecast"
								/>
								<Line
									type="monotone"
									dataKey="budget"
									stroke="#64748b"
									strokeWidth={2}
									strokeDasharray="3 3"
									dot={false}
									name="Budget"
								/>
							</LineChart>
						</ResponsiveContainer>
					</div>
					<div className="mt-4 p-3 bg-indigo-900/30 rounded-lg border border-indigo-800">
						<div className="flex items-center gap-2">
							<TrendingUp className="w-4 h-4 text-indigo-400" />
							<p className="text-sm text-slate-200">
								<span className="font-semibold">
									AI Insight:
								</span>{" "}
								Spending is trending 8% below forecast. Consider
								reallocating budget to Q4 initiatives.
							</p>
						</div>
					</div>
				</CardContent>
			</Card>
		</motion.div>
	);
}
