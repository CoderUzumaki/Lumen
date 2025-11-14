"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PieChart as PieChartIcon } from "lucide-react";
import { motion } from "framer-motion";
import {
	PieChart,
	Pie,
	Cell,
	ResponsiveContainer,
	Tooltip,
	Legend,
} from "recharts";

// Mock data - Replace with API call
const mockCategoryData = [
	{ name: "Software", value: 45000, percentage: 35 },
	{ name: "Office Supplies", value: 25000, percentage: 19 },
	{ name: "Cloud Services", value: 22000, percentage: 17 },
	{ name: "Utilities", value: 18000, percentage: 14 },
	{ name: "Equipment", value: 12000, percentage: 9 },
	{ name: "Others", value: 8000, percentage: 6 },
];

const COLORS = [
	"#4f46e5",
	"#f97316",
	"#10b981",
	"#06b6d4",
	"#8b5cf6",
	"#94a3b8",
];

const cardVariants = {
	hidden: { opacity: 0, y: 20 },
	visible: {
		opacity: 1,
		y: 0,
		transition: {
			duration: 0.5,
			ease: "easeOut",
			delay: 0.6,
		},
	},
};

const CustomTooltip = ({ active, payload }: any) => {
	if (active && payload && payload.length) {
		return (
			<div className="bg-slate-800 p-3 border border-slate-600 rounded-lg shadow-lg">
				<p className="font-semibold text-white">{payload[0].name}</p>
				<p className="text-sm text-slate-300">
					€{payload[0].value.toLocaleString()}
				</p>
				<p className="text-sm text-slate-300">
					{payload[0].payload.percentage}%
				</p>
			</div>
		);
	}
	return null;
};

const renderCustomLabel = (entry: any) => {
	return `${entry.percentage}%`;
};

export default function CategoryPieChart() {
	return (
		<motion.div
			variants={cardVariants}
			initial="hidden"
			animate="visible"
			className="h-full"
		>
			<Card className="border-slate-800 shadow-lg hover:shadow-xl transition-all duration-300 bg-slate-900/50 backdrop-blur-sm h-full">
				<CardHeader className="pb-3">
					<CardTitle className="text-lg font-semibold text-white flex items-center gap-2">
						<PieChartIcon className="w-5 h-5 text-purple-400" />
						Category Breakdown
					</CardTitle>
				</CardHeader>
				<CardContent>
					<div className="h-[250px] w-full">
						<ResponsiveContainer width="100%" height="100%">
							<PieChart>
								<Pie
									data={mockCategoryData}
									cx="50%"
									cy="50%"
									labelLine={false}
									label={renderCustomLabel}
									outerRadius={80}
									fill="#8884d8"
									dataKey="value"
								>
									{mockCategoryData.map((entry, index) => (
										<Cell
											key={`cell-${index}`}
											fill={COLORS[index % COLORS.length]}
										/>
									))}
								</Pie>
								<Tooltip content={<CustomTooltip />} />
							</PieChart>
						</ResponsiveContainer>
					</div>

					{/* Legend */}
					<div className="mt-4 space-y-2">
						{mockCategoryData.map((category, index) => (
							<motion.div
								key={category.name}
								initial={{ opacity: 0, x: -10 }}
								animate={{ opacity: 1, x: 0 }}
								transition={{
									duration: 0.3,
									delay: 0.7 + index * 0.1,
								}}
								className="flex items-center justify-between p-2 rounded hover:bg-slate-700/50 transition-colors"
							>
								<div className="flex items-center gap-2">
									<div
										className="w-3 h-3 rounded-full"
										style={{
											backgroundColor: COLORS[index],
										}}
									></div>
									<span className="text-sm text-slate-200">
										{category.name}
									</span>
								</div>
								<div className="text-right">
									<p className="text-sm font-semibold text-white">
										€{category.value.toLocaleString()}
									</p>
									<p className="text-xs text-slate-400">
										{category.percentage}%
									</p>
								</div>
							</motion.div>
						))}
					</div>

					{/* Total */}
					<div className="mt-4 pt-4 border-t border-slate-700">
						<div className="flex items-center justify-between">
							<span className="text-sm font-semibold text-slate-200">
								Total Spending
							</span>
							<span className="text-lg font-bold text-white">
								€
								{mockCategoryData
									.reduce((sum, cat) => sum + cat.value, 0)
									.toLocaleString()}
							</span>
						</div>
					</div>
				</CardContent>
			</Card>
		</motion.div>
	);
}
