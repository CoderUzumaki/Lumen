"use client";

import { useState, useEffect, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import { DashboardShell } from "@/components/dashboard-shell";
import AnalyticsCards from "@/components/analytics/analyticsCards";
import SpendingTrendChart from "@/components/analytics/spendingTrendChart";
import { Button } from "@/components/ui/button";
import { Calendar, ChevronLeft, ChevronRight } from "lucide-react";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";

type TimeRange = "weekly" | "monthly" | "yearly";

interface SelectedPeriod {
	year: number;
	month?: number; // 0-11 (for monthly)
	week?: number; // 1-52 (for weekly)
}

export default function AnalyticsContent() {
	const searchParams = useSearchParams();
	const tabParam = searchParams.get("tab") as TimeRange | null;

	const [timeRange, setTimeRange] = useState<TimeRange>(
		tabParam || "monthly"
	);
	const now = new Date();
	const [selectedPeriod, setSelectedPeriod] = useState<SelectedPeriod>({
		year: now.getFullYear(),
		month: now.getMonth(),
	});

	// Generate period options based on time range
	const generateYears = () => {
		const currentYear = new Date().getFullYear();
		const years = [];
		for (let i = currentYear; i >= currentYear - 5; i--) {
			years.push(i);
		}
		return years;
	};

	const months = [
		"January",
		"February",
		"March",
		"April",
		"May",
		"June",
		"July",
		"August",
		"September",
		"October",
		"November",
		"December",
	];

	const generateWeeks = () => {
		const weeks = [];
		for (let i = 1; i <= 52; i++) {
			weeks.push(i);
		}
		return weeks;
	};

	const getCurrentWeek = useCallback(() => {
		const now = new Date();
		const start = new Date(now.getFullYear(), 0, 1);
		const diff = now.getTime() - start.getTime();
		const oneWeek = 1000 * 60 * 60 * 24 * 7;
		return Math.ceil(diff / oneWeek);
	}, []);

	const handlePeriodChange = (type: string, value: string) => {
		if (type === "year") {
			setSelectedPeriod({ ...selectedPeriod, year: parseInt(value) });
		} else if (type === "month") {
			setSelectedPeriod({ ...selectedPeriod, month: parseInt(value) });
		} else if (type === "week") {
			setSelectedPeriod({ ...selectedPeriod, week: parseInt(value) });
		}
	};

	const handleTimeRangeChange = useCallback(
		(range: TimeRange) => {
			setTimeRange(range);
			const currentDate = new Date();
			if (range === "monthly") {
				setSelectedPeriod({
					year: currentDate.getFullYear(),
					month: currentDate.getMonth(),
				});
			} else if (range === "weekly") {
				setSelectedPeriod({
					year: currentDate.getFullYear(),
					week: getCurrentWeek(),
				});
			} else {
				setSelectedPeriod({ year: currentDate.getFullYear() });
			}
		},
		[getCurrentWeek]
	);

	// Initialize time range and period based on URL parameter
	useEffect(() => {
		if (tabParam && ["weekly", "monthly", "yearly"].includes(tabParam)) {
			handleTimeRangeChange(tabParam);
		}
	}, [tabParam, handleTimeRangeChange]);

	const getPeriodLabel = () => {
		if (timeRange === "yearly") {
			return `Year ${selectedPeriod.year}`;
		} else if (
			timeRange === "monthly" &&
			selectedPeriod.month !== undefined
		) {
			return `${months[selectedPeriod.month]} ${selectedPeriod.year}`;
		} else if (timeRange === "weekly" && selectedPeriod.week) {
			return `Week ${selectedPeriod.week}, ${selectedPeriod.year}`;
		}
		return "";
	};

	const navigatePeriod = (direction: "prev" | "next") => {
		const newPeriod = { ...selectedPeriod };
		if (timeRange === "yearly") {
			newPeriod.year += direction === "next" ? 1 : -1;
		} else if (timeRange === "monthly" && newPeriod.month !== undefined) {
			if (direction === "next") {
				if (newPeriod.month === 11) {
					newPeriod.month = 0;
					newPeriod.year++;
				} else {
					newPeriod.month++;
				}
			} else {
				if (newPeriod.month === 0) {
					newPeriod.month = 11;
					newPeriod.year--;
				} else {
					newPeriod.month--;
				}
			}
		} else if (timeRange === "weekly" && newPeriod.week) {
			if (direction === "next") {
				if (newPeriod.week === 52) {
					newPeriod.week = 1;
					newPeriod.year++;
				} else {
					newPeriod.week++;
				}
			} else {
				if (newPeriod.week === 1) {
					newPeriod.week = 52;
					newPeriod.year--;
				} else {
					newPeriod.week--;
				}
			}
		}
		setSelectedPeriod(newPeriod);
	};

	const toolbar = (
		<div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
			<div className="flex flex-wrap items-center gap-2">
				{(["weekly", "monthly", "yearly"] as TimeRange[]).map((range) => (
					<Button
						key={range}
						variant={timeRange === range ? "default" : "outline"}
						onClick={() => handleTimeRangeChange(range)}
						className="rounded-full px-4"
					>
						{range[0].toUpperCase()}
						{range.slice(1)}
					</Button>
				))}
			</div>

			<div className="flex flex-wrap items-center gap-3 rounded-2xl border border-border/70 bg-background/60 p-2">
				<Button
					variant="ghost"
					size="icon"
					onClick={() => navigatePeriod("prev")}
				>
					<ChevronLeft className="w-4 h-4" />
				</Button>

				{timeRange === "yearly" && (
					<Select
						value={selectedPeriod.year.toString()}
						onValueChange={(value) =>
							handlePeriodChange("year", value)
						}
					>
						<SelectTrigger className="w-[140px]">
							<SelectValue />
						</SelectTrigger>
						<SelectContent>
							{generateYears().map((year) => (
								<SelectItem key={year} value={year.toString()}>
									{year}
								</SelectItem>
							))}
						</SelectContent>
					</Select>
				)}

				{timeRange === "monthly" && (
					<>
						<Select
							value={selectedPeriod.month?.toString()}
							onValueChange={(value) =>
								handlePeriodChange("month", value)
							}
						>
							<SelectTrigger className="w-[150px]">
								<SelectValue />
							</SelectTrigger>
							<SelectContent>
								{months.map((month, idx) => (
									<SelectItem key={idx} value={idx.toString()}>
										{month}
									</SelectItem>
								))}
							</SelectContent>
						</Select>
						<Select
							value={selectedPeriod.year.toString()}
							onValueChange={(value) =>
								handlePeriodChange("year", value)
							}
						>
							<SelectTrigger className="w-[110px]">
								<SelectValue />
							</SelectTrigger>
							<SelectContent>
								{generateYears().map((year) => (
									<SelectItem key={year} value={year.toString()}>
										{year}
									</SelectItem>
								))}
							</SelectContent>
						</Select>
					</>
				)}

				{timeRange === "weekly" && (
					<>
						<Select
							value={selectedPeriod.week?.toString()}
							onValueChange={(value) =>
								handlePeriodChange("week", value)
							}
						>
							<SelectTrigger className="w-[130px]">
								<SelectValue placeholder="Week" />
							</SelectTrigger>
							<SelectContent>
								{generateWeeks().map((week) => (
									<SelectItem key={week} value={week.toString()}>
										Week {week}
									</SelectItem>
								))}
							</SelectContent>
						</Select>
						<Select
							value={selectedPeriod.year.toString()}
							onValueChange={(value) =>
								handlePeriodChange("year", value)
							}
						>
							<SelectTrigger className="w-[110px]">
								<SelectValue />
							</SelectTrigger>
							<SelectContent>
								{generateYears().map((year) => (
									<SelectItem key={year} value={year.toString()}>
										{year}
									</SelectItem>
								))}
							</SelectContent>
						</Select>
					</>
				)}

				<Button
					variant="ghost"
					size="icon"
					onClick={() => navigatePeriod("next")}
				>
					<ChevronRight className="w-4 h-4" />
				</Button>
			</div>
		</div>
	);

	return (
		<DashboardShell
			title="Spending Analytics"
			description="Compare cash outflow across weekly, monthly, and yearly periods to spot volatility, vendor concentration, and cost drift."
			eyebrow="Spend Analysis"
			toolbar={toolbar}
			actions={
				<div className="inline-flex items-center gap-2 rounded-full border border-border/70 bg-background/60 px-4 py-2 text-sm text-muted-foreground">
					<Calendar className="h-4 w-4 text-primary" />
					<span>{getPeriodLabel()}</span>
				</div>
			}
		>
			<AnalyticsCards
				timeRange={timeRange}
				selectedPeriod={selectedPeriod}
			/>
			<SpendingTrendChart
				timeRange={timeRange}
				selectedPeriod={selectedPeriod}
			/>
		</DashboardShell>
	);
}
