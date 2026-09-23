"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PieChart as PieChartIcon } from "lucide-react";
import { motion } from "framer-motion";
import { useState, useEffect } from "react";
import { transactionApi, tokenManager } from "@/lib/api/client";
import {
	PieChart,
	Pie,
	Cell,
	ResponsiveContainer,
	Tooltip,
	Legend,
} from "recharts";

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
			ease: [0.4, 0, 0.2, 1] as any,
			delay: 0.6,
		},
	},
};

const CustomTooltip = ({ active, payload }: any) => {
	if (active && payload && payload.length) {
		return (
			<div className="rounded-xl border border-border/70 bg-card/95 p-3 shadow-xl shadow-black/20">
				<p className="font-semibold text-foreground">{payload[0].name}</p>
				<p className="text-sm text-muted-foreground">
					₹{payload[0].value.toLocaleString("en-IN")}
				</p>
				<p className="text-sm text-muted-foreground">
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
	const [categoryData, setCategoryData] = useState<any[]>([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		const fetchCategoryData = async () => {
			try {
				setLoading(true);
				const user = tokenManager.getUser();
				if (!user?.id) {
					setError("User not found");
					return;
				}

				const response = await transactionApi.getTransactions({
					page: 1,
					page_size: 1000,
				});

				const transactions = response.data || [];

				// Aggregate by category
				const categoryMap: { [key: string]: number } = {};
				transactions.forEach((transaction: any) => {
					const category = transaction.category || "Uncategorized";
					const amount = parseFloat(transaction.total_amount || 0);
					categoryMap[category] =
						(categoryMap[category] || 0) + amount;
				});

				// Calculate total and percentages
				const total = Object.values(categoryMap).reduce(
					(sum, val) => sum + val,
					0
				);
				const aggregatedData = Object.entries(categoryMap).map(
					([name, value]) => ({
						name,
						value,
						percentage:
							total > 0
								? ((value / total) * 100).toFixed(1)
								: "0",
					})
				);

				setCategoryData(aggregatedData);
				setError(null);
			} catch (err: any) {
				console.error("Failed to fetch category data:", err);
				setError(err.message || "Failed to load data");
			} finally {
				setLoading(false);
			}
		};

		fetchCategoryData();
	}, []);

	if (loading) {
		return (
			<Card className="h-full border-border/70 bg-card/80 shadow-lg shadow-black/10">
				<CardContent className="flex items-center justify-center h-[400px]">
					<p className="text-muted-foreground">Loading category data...</p>
				</CardContent>
			</Card>
		);
	}

	if (error) {
		return (
			<Card className="h-full border-border/70 bg-card/80 shadow-lg shadow-black/10">
				<CardContent className="flex items-center justify-center h-[400px]">
					<p className="text-rose-300">{error}</p>
				</CardContent>
			</Card>
		);
	}

	if (categoryData.length === 0) {
		return (
			<Card className="h-full border-border/70 bg-card/80 shadow-lg shadow-black/10">
				<CardContent className="flex items-center justify-center h-[400px]">
					<p className="text-muted-foreground">No category data available</p>
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
			<Card className="h-full border-border/70 bg-card/80 shadow-lg shadow-black/10 transition-all duration-300 hover:shadow-xl hover:shadow-black/10">
				<CardHeader className="pb-3">
					<CardTitle className="flex items-center gap-2 text-lg font-semibold text-foreground">
						<PieChartIcon className="h-5 w-5 text-primary" />
						Category Breakdown
					</CardTitle>
				</CardHeader>
				<CardContent>
					<div className="h-[250px] w-full">
						<ResponsiveContainer width="100%" height="100%">
							<PieChart>
								<Pie
									data={categoryData}
									cx="50%"
									cy="50%"
									labelLine={false}
									label={renderCustomLabel}
									outerRadius={80}
									fill="#8884d8"
									dataKey="value"
								>
									{categoryData.map((entry, index) => (
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
						{categoryData.map((category, index) => (
							<motion.div
								key={category.name}
								initial={{ opacity: 0, x: -10 }}
								animate={{ opacity: 1, x: 0 }}
								transition={{
									duration: 0.3,
									delay: 0.7 + index * 0.1,
								}}
								className="flex items-center justify-between rounded-lg p-2 transition-colors hover:bg-accent/60"
							>
								<div className="flex items-center gap-2">
									<div
										className="w-3 h-3 rounded-full"
										style={{
											backgroundColor: COLORS[index],
										}}
									></div>
									<span className="text-sm text-muted-foreground">
										{category.name}
									</span>
								</div>
								<div className="text-right">
									<p className="text-sm font-semibold text-foreground">
										₹
										{category.value.toLocaleString("en-IN")}
									</p>
									<p className="text-xs text-muted-foreground">
										{category.percentage}%
									</p>
								</div>
							</motion.div>
						))}
					</div>

					{/* Total */}
					<div className="mt-4 border-t border-border/70 pt-4">
						<div className="flex items-center justify-between">
							<span className="text-sm font-semibold text-muted-foreground">
								Total Spending
							</span>
							<span className="text-lg font-bold text-foreground">
								₹
								{categoryData
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
