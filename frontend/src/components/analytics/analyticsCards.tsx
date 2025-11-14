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
import { useEffect, useState } from "react";
import { analyticsApi, tokenManager } from "@/lib/api/client";

interface SelectedPeriod {
	year: number;
	month?: number;
	week?: number;
}

interface AnalyticsCardsProps {
	timeRange: "weekly" | "monthly" | "yearly";
	selectedPeriod: SelectedPeriod;
}

interface AnalyticsData {
	avgSpending: number;
	maxSpending: number;
	minSpending: number;
	totalSpending: number;
	previousTotal: number;
	avgChange: number;
	maxChange: number;
	minChange: number;
}

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
	const [data, setData] = useState<AnalyticsData>({
		avgSpending: 0,
		maxSpending: 0,
		minSpending: 0,
		totalSpending: 0,
		previousTotal: 0,
		avgChange: 0,
		maxChange: 0,
		minChange: 0,
	});
	const [loading, setLoading] = useState(true);

	useEffect(() => {
		const fetchAnalytics = async () => {
			try {
				setLoading(true);
				const user = tokenManager.getUser();
				if (!user?.id) return;

				const response = await analyticsApi.getTimeRangeAnalytics(
					user.id as string,
					timeRange,
					selectedPeriod.year,
					selectedPeriod.month,
					selectedPeriod.week
				);

				if (response.success) {
					const current = response.current_period;
					const previous = response.previous_period;

					setData({
						avgSpending: current.avg_spending || 0,
						maxSpending: current.max_spending || 0,
						minSpending: current.min_spending || 0,
						totalSpending: current.total_spending || 0,
						previousTotal: previous.total_spending || 0,
						avgChange:
							previous.avg_spending && previous.avg_spending !== 0
								? ((current.avg_spending -
										previous.avg_spending) /
										previous.avg_spending) *
								  100
								: 0,
						maxChange:
							previous.max_spending && previous.max_spending !== 0
								? ((current.max_spending -
										previous.max_spending) /
										previous.max_spending) *
								  100
								: 0,
						minChange:
							previous.min_spending && previous.min_spending !== 0
								? ((current.min_spending -
										previous.min_spending) /
										previous.min_spending) *
								  100
								: 0,
					});
				}
			} catch (error) {
				console.error("Error fetching analytics:", error);
			} finally {
				setLoading(false);
			}
		};

		fetchAnalytics();
	}, [timeRange, selectedPeriod]);

	const trendChange =
		data.previousTotal !== 0
			? ((data.totalSpending - data.previousTotal) / data.previousTotal) *
			  100
			: 0;
	const trendDifference = data.totalSpending - data.previousTotal;
	const previousLabel = getPreviousPeriodLabel(timeRange, selectedPeriod);

	if (loading) {
		return (
			<div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
				{[...Array(4)].map((_, i) => (
					<Card key={i} className="animate-pulse">
						<CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
							<div className="h-4 w-24 bg-muted rounded"></div>
							<div className="h-4 w-4 bg-muted rounded"></div>
						</CardHeader>
						<CardContent>
							<div className="h-8 w-32 bg-muted rounded mb-2"></div>
							<div className="h-4 w-full bg-muted rounded"></div>
						</CardContent>
					</Card>
				))}
			</div>
		);
	}

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
