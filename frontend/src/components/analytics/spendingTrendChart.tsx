"use client";

import {
	Area,
	AreaChart,
	CartesianGrid,
	Tooltip,
	XAxis,
	YAxis,
	ResponsiveContainer,
	Legend,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { BarChart3 } from "lucide-react";

interface SelectedPeriod {
	year: number;
	month?: number;
	week?: number;
}

interface SpendingTrendChartProps {
	timeRange: "weekly" | "monthly" | "yearly";
	selectedPeriod: SelectedPeriod;
}

// Mock data for different time ranges - comparing current vs previous period
const getMockChartData = (
	timeRange: string,
	selectedPeriod: SelectedPeriod
) => {
	const data = {
		weekly: [
			{
				date: "Mon",
				currentSpending: 120.5,
				previousSpending: 135.2,
				transactions: 5,
			},
			{
				date: "Tue",
				currentSpending: 245.75,
				previousSpending: 198.4,
				transactions: 8,
			},
			{
				date: "Wed",
				currentSpending: 189.25,
				previousSpending: 225.6,
				transactions: 6,
			},
			{
				date: "Thu",
				currentSpending: 356.0,
				previousSpending: 320.5,
				transactions: 12,
			},
			{
				date: "Fri",
				currentSpending: 425.5,
				previousSpending: 380.2,
				transactions: 15,
			},
			{
				date: "Sat",
				currentSpending: 512.25,
				previousSpending: 475.8,
				transactions: 18,
			},
			{
				date: "Sun",
				currentSpending: 178.0,
				previousSpending: 195.3,
				transactions: 7,
			},
		],
		monthly: [
			{
				date: "Week 1",
				currentSpending: 1250.0,
				previousSpending: 1180.0,
				transactions: 45,
			},
			{
				date: "Week 2",
				currentSpending: 1580.5,
				previousSpending: 1720.3,
				transactions: 52,
			},
			{
				date: "Week 3",
				currentSpending: 1420.75,
				previousSpending: 1350.8,
				transactions: 48,
			},
			{
				date: "Week 4",
				currentSpending: 1890.25,
				previousSpending: 2100.5,
				transactions: 65,
			},
		],
		yearly: [
			{
				date: "Jan",
				currentSpending: 5240.0,
				previousSpending: 4890.0,
				transactions: 125,
			},
			{
				date: "Feb",
				currentSpending: 4890.5,
				previousSpending: 5120.0,
				transactions: 118,
			},
			{
				date: "Mar",
				currentSpending: 6120.75,
				previousSpending: 5650.0,
				transactions: 145,
			},
			{
				date: "Apr",
				currentSpending: 5580.0,
				previousSpending: 5890.0,
				transactions: 132,
			},
			{
				date: "May",
				currentSpending: 6890.25,
				previousSpending: 6320.0,
				transactions: 156,
			},
			{
				date: "Jun",
				currentSpending: 5670.5,
				previousSpending: 6100.0,
				transactions: 138,
			},
			{
				date: "Jul",
				currentSpending: 7240.0,
				previousSpending: 6890.0,
				transactions: 168,
			},
			{
				date: "Aug",
				currentSpending: 6580.75,
				previousSpending: 7020.0,
				transactions: 152,
			},
			{
				date: "Sep",
				currentSpending: 5920.5,
				previousSpending: 5450.0,
				transactions: 142,
			},
			{
				date: "Oct",
				currentSpending: 6340.25,
				previousSpending: 6780.0,
				transactions: 148,
			},
			{
				date: "Nov",
				currentSpending: 7120.0,
				previousSpending: 6540.0,
				transactions: 165,
			},
			{
				date: "Dec",
				currentSpending: 8450.5,
				previousSpending: 7890.0,
				transactions: 185,
			},
		],
	};

	return data[timeRange as keyof typeof data];
};

const getPeriodLabels = (timeRange: string, selectedPeriod: SelectedPeriod) => {
	if (timeRange === "yearly") {
		return {
			current: `${selectedPeriod.year}`,
			previous: `${selectedPeriod.year - 1}`,
		};
	} else if (timeRange === "monthly" && selectedPeriod.month !== undefined) {
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
		const prevMonth =
			selectedPeriod.month === 0 ? 11 : selectedPeriod.month - 1;
		const prevYear =
			selectedPeriod.month === 0
				? selectedPeriod.year - 1
				: selectedPeriod.year;
		return {
			current: `${months[selectedPeriod.month]} ${selectedPeriod.year}`,
			previous: `${months[prevMonth]} ${prevYear}`,
		};
	} else if (timeRange === "weekly" && selectedPeriod.week) {
		const prevWeek =
			selectedPeriod.week === 1 ? 52 : selectedPeriod.week - 1;
		const prevYear =
			selectedPeriod.week === 1
				? selectedPeriod.year - 1
				: selectedPeriod.year;
		return {
			current: `Week ${selectedPeriod.week}, ${selectedPeriod.year}`,
			previous: `Week ${prevWeek}, ${prevYear}`,
		};
	}
	return { current: "Current Period", previous: "Previous Period" };
};

const CustomTooltip = ({ active, payload, label }: any) => {
	if (active && payload && payload.length) {
		return (
			<div className="bg-white p-4 rounded-lg shadow-lg border">
				<p className="font-semibold text-sm mb-2">{label}</p>
				{payload.map((entry: any, index: number) => (
					<p
						key={index}
						className="text-xs"
						style={{ color: entry.color }}
					>
						{entry.name === "currentSpending"
							? "Current Period"
							: "Previous Period"}
						: $
						{entry.value.toLocaleString("en-US", {
							minimumFractionDigits: 2,
							maximumFractionDigits: 2,
						})}
					</p>
				))}
			</div>
		);
	}
	return null;
};

export default function SpendingTrendChart({
	timeRange,
	selectedPeriod,
}: SpendingTrendChartProps) {
	const data = getMockChartData(timeRange, selectedPeriod);
	const labels = getPeriodLabels(timeRange, selectedPeriod);

	return (
		<Card className="w-full">
			<CardHeader>
				<CardTitle className="flex items-center gap-2">
					<BarChart3 className="w-5 h-5 text-primary" />
					Spending Comparison
				</CardTitle>
				<p className="text-sm text-muted-foreground">
					Comparing{" "}
					<span className="font-semibold text-primary">
						{labels.current}
					</span>{" "}
					vs{" "}
					<span className="font-semibold text-muted-foreground/80">
						{labels.previous}
					</span>
				</p>
			</CardHeader>
			<CardContent>
				<ResponsiveContainer width="100%" height={400}>
					<AreaChart
						data={data}
						margin={{ top: 10, right: 30, left: 0, bottom: 0 }}
					>
						<defs>
							<linearGradient
								id="colorSpending"
								x1="0"
								y1="0"
								x2="0"
								y2="1"
							>
								<stop
									offset="5%"
									stopColor="#8884d8"
									stopOpacity={0.8}
								/>
								<stop
									offset="95%"
									stopColor="#8884d8"
									stopOpacity={0}
								/>
							</linearGradient>
							<linearGradient
								id="colorIncome"
								x1="0"
								y1="0"
								x2="0"
								y2="1"
							>
								<stop
									offset="5%"
									stopColor="#82ca9d"
									stopOpacity={0.8}
								/>
								<stop
									offset="95%"
									stopColor="#82ca9d"
									stopOpacity={0}
								/>
							</linearGradient>
						</defs>
						<CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
						<XAxis
							dataKey="date"
							tick={{ fontSize: 12 }}
							tickLine={false}
						/>
						<YAxis
							tick={{ fontSize: 12 }}
							tickLine={false}
							tickFormatter={(value) => `$${value}`}
						/>
						<Tooltip content={<CustomTooltip />} />
						<Legend
							wrapperStyle={{ paddingTop: "20px" }}
							iconType="circle"
						/>
						<Area
							type="monotone"
							dataKey="currentSpending"
							stroke="#8884d8"
							fillOpacity={1}
							fill="url(#colorSpending)"
							strokeWidth={2}
							name="currentSpending"
							animationDuration={1000}
						/>
						<Area
							type="monotone"
							dataKey="previousSpending"
							stroke="#82ca9d"
							fillOpacity={1}
							fill="url(#colorIncome)"
							strokeWidth={2}
							name="previousSpending"
							animationDuration={1000}
						/>
					</AreaChart>
				</ResponsiveContainer>
			</CardContent>
		</Card>
	);
}
