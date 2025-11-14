"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
	ArrowUpIcon,
	ArrowDownIcon,
	DollarSign,
	TrendingUp,
	TrendingDown,
	Activity,
} from "lucide-react";

interface SelectedPeriod {
	year: number;
	month?: number;
	week?: number;
}

interface AnalyticsCardsProps {
	timeRange: "weekly" | "monthly" | "yearly";
	selectedPeriod: SelectedPeriod;
}

// Mock data - this will be replaced by API calls
const getMockData = (timeRange: string, selectedPeriod: SelectedPeriod) => {
	const data = {
		weekly: {
			avgSpending: 450.75,
			maxSpending: 1250.0,
			minSpending: 15.5,
			totalSpending: 3155.25,
			previousTotal: 2815.5,
			avgChange: 12.5,
			maxChange: -8.3,
			minChange: 22.1,
		},
		monthly: {
			avgSpending: 1850.25,
			maxSpending: 4500.0,
			minSpending: 15.5,
			totalSpending: 55507.5,
			previousTotal: 58621.0,
			avgChange: -5.2,
			maxChange: 15.8,
			minChange: -10.5,
		},
		yearly: {
			avgSpending: 22500.0,
			maxSpending: 45000.0,
			minSpending: 150.0,
			totalSpending: 270000.0,
			previousTotal: 248400.0,
			avgChange: 8.7,
			maxChange: 12.4,
			minChange: -15.2,
		},
	};

	return data[timeRange as keyof typeof data];
};

const getPreviousPeriodLabel = (
	timeRange: string,
	selectedPeriod: SelectedPeriod
) => {
	if (timeRange === "yearly") {
		return `${selectedPeriod.year - 1}`;
	} else if (timeRange === "monthly" && selectedPeriod.month !== undefined) {
		const prevMonth =
			selectedPeriod.month === 0 ? 11 : selectedPeriod.month - 1;
		const prevYear =
			selectedPeriod.month === 0
				? selectedPeriod.year - 1
				: selectedPeriod.year;
		const months = [
			"Jan",
			"Feb",
			"Mar",
			"Apr",
			"May",
			"Jun",
			"Jul",
			"Aug",
			"Sep",
			"Oct",
			"Nov",
			"Dec",
		];
		return `${months[prevMonth]} ${prevYear}`;
	} else if (timeRange === "weekly" && selectedPeriod.week) {
		const prevWeek =
			selectedPeriod.week === 1 ? 52 : selectedPeriod.week - 1;
		const prevYear =
			selectedPeriod.week === 1
				? selectedPeriod.year - 1
				: selectedPeriod.year;
		return `Week ${prevWeek}, ${prevYear}`;
	}
	return "previous period";
};

export default function AnalyticsCards({
	timeRange,
	selectedPeriod,
}: AnalyticsCardsProps) {
	const data = getMockData(timeRange, selectedPeriod);
	const trendChange =
		((data.totalSpending - data.previousTotal) / data.previousTotal) * 100;
	const trendDifference = data.totalSpending - data.previousTotal;
	const previousLabel = getPreviousPeriodLabel(timeRange, selectedPeriod);

	const cards = [
		{
			title: "Average Spending",
			value: data.avgSpending,
			change: data.avgChange,
			icon: DollarSign,
			description: `vs. ${previousLabel}`,
		},
		{
			title: "Maximum Spending",
			value: data.maxSpending,
			change: data.maxChange,
			icon: TrendingUp,
			description: "Highest transaction",
		},
		{
			title: "Minimum Spending",
			value: data.minSpending,
			change: data.minChange,
			icon: TrendingDown,
			description: "Lowest transaction",
		},
		{
			title: "Spending Trend",
			value: Math.abs(trendDifference),
			change: trendChange,
			icon: Activity,
			description:
				trendChange >= 0
					? `more than ${previousLabel}`
					: `less than ${previousLabel}`,
			isTrend: true,
		},
	];

	return (
		<div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
			{cards.map((card, index) => {
				const isPositive = card.change > 0;
				const Icon = card.icon;

				return (
					<Card
						key={index}
						className="hover:shadow-lg transition-shadow"
					>
						<CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
							<CardTitle className="text-sm font-medium">
								{card.title}
							</CardTitle>
							<Icon className="h-4 w-4 text-muted-foreground" />
						</CardHeader>
						<CardContent>
							<div className="text-2xl font-bold">
								{card.isTrend && (
									<span
										className={
											isPositive
												? "text-red-600"
												: "text-green-600"
										}
									>
										{isPositive ? "+" : "-"}
									</span>
								)}
								$
								{card.value.toLocaleString("en-US", {
									minimumFractionDigits: 2,
									maximumFractionDigits: 2,
								})}
							</div>
							<div className="flex items-center gap-1 text-xs text-muted-foreground mt-1">
								{isPositive ? (
									<ArrowUpIcon
										className={`h-3 w-3 ${
											card.isTrend
												? "text-red-600"
												: "text-green-600"
										}`}
									/>
								) : (
									<ArrowDownIcon
										className={`h-3 w-3 ${
											card.isTrend
												? "text-green-600"
												: "text-red-600"
										}`}
									/>
								)}
								<span
									className={
										card.isTrend
											? isPositive
												? "text-red-600"
												: "text-green-600"
											: isPositive
											? "text-green-600"
											: "text-red-600"
									}
								>
									{Math.abs(card.change).toFixed(1)}%
								</span>
								<span className="ml-1">{card.description}</span>
							</div>
						</CardContent>
					</Card>
				);
			})}
		</div>
	);
}
