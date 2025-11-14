"use client";

import { useState, useEffect, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import { SidebarProvider } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/app-sidebar";
import { Separator } from "@/components/ui/separator";
import { SidebarInset, SidebarTrigger } from "@/components/ui/sidebar";
import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbLink,
	BreadcrumbList,
	BreadcrumbPage,
	BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import AnalyticsCards from "@/components/analytics/analyticsCards";
import SpendingTrendChart from "@/components/analytics/spendingTrendChart";
import { Button } from "@/components/ui/button";
import { Calendar, TrendingUp, ChevronLeft, ChevronRight } from "lucide-react";
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
	const [selectedPeriod, setSelectedPeriod] = useState<SelectedPeriod>({
		year: new Date().getFullYear(),
		month: new Date().getMonth(),
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

	return (
		<SidebarProvider>
			<AppSidebar />
			<SidebarInset>
				<header className="flex h-16 shrink-0 items-center gap-2 border-b px-4">
					<SidebarTrigger className="-ml-1" />
					<Separator orientation="vertical" className="mr-2 h-4" />
					<Breadcrumb>
						<BreadcrumbList>
							<BreadcrumbItem className="hidden md:block">
								<BreadcrumbLink href="/">Home</BreadcrumbLink>
							</BreadcrumbItem>
							<BreadcrumbSeparator className="hidden md:block" />
							<BreadcrumbItem>
								<BreadcrumbPage>Analytics</BreadcrumbPage>
							</BreadcrumbItem>
						</BreadcrumbList>
					</Breadcrumb>
				</header>

				<div className="flex flex-1 flex-col gap-4 p-4 pt-0">
					{/* Page Header with Time Range Tabs */}
					<div className="flex flex-col gap-4 py-4">
						<div className="flex items-center justify-between flex-wrap gap-4">
							<div>
								<h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
									<TrendingUp className="w-8 h-8 text-primary" />
									Spending Analytics
								</h1>
								<p className="text-muted-foreground mt-1">
									Compare spending patterns across periods
								</p>
							</div>
							<div className="flex items-center gap-3 bg-muted/50 p-2 rounded-lg">
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
										<SelectTrigger className="w-[120px]">
											<SelectValue />
										</SelectTrigger>
										<SelectContent>
											{generateYears().map((year) => (
												<SelectItem
													key={year}
													value={year.toString()}
												>
													{year}
												</SelectItem>
											))}
										</SelectContent>
									</Select>
								)}

								{timeRange === "monthly" && (
									<div className="flex gap-2">
										<Select
											value={selectedPeriod.month?.toString()}
											onValueChange={(value) =>
												handlePeriodChange(
													"month",
													value
												)
											}
										>
											<SelectTrigger className="w-[140px]">
												<SelectValue />
											</SelectTrigger>
											<SelectContent>
												{months.map((month, idx) => (
													<SelectItem
														key={idx}
														value={idx.toString()}
													>
														{month}
													</SelectItem>
												))}
											</SelectContent>
										</Select>
										<Select
											value={selectedPeriod.year.toString()}
											onValueChange={(value) =>
												handlePeriodChange(
													"year",
													value
												)
											}
										>
											<SelectTrigger className="w-[100px]">
												<SelectValue />
											</SelectTrigger>
											<SelectContent>
												{generateYears().map((year) => (
													<SelectItem
														key={year}
														value={year.toString()}
													>
														{year}
													</SelectItem>
												))}
											</SelectContent>
										</Select>
									</div>
								)}

								{timeRange === "weekly" && (
									<div className="flex gap-2">
										<Select
											value={selectedPeriod.week?.toString()}
											onValueChange={(value) =>
												handlePeriodChange(
													"week",
													value
												)
											}
										>
											<SelectTrigger className="w-[120px]">
												<SelectValue placeholder="Week" />
											</SelectTrigger>
											<SelectContent>
												{generateWeeks().map((week) => (
													<SelectItem
														key={week}
														value={week.toString()}
													>
														Week {week}
													</SelectItem>
												))}
											</SelectContent>
										</Select>
										<Select
											value={selectedPeriod.year.toString()}
											onValueChange={(value) =>
												handlePeriodChange(
													"year",
													value
												)
											}
										>
											<SelectTrigger className="w-[100px]">
												<SelectValue />
											</SelectTrigger>
											<SelectContent>
												{generateYears().map((year) => (
													<SelectItem
														key={year}
														value={year.toString()}
													>
														{year}
													</SelectItem>
												))}
											</SelectContent>
										</Select>
									</div>
								)}

								<Button
									variant="ghost"
									size="icon"
									onClick={() => navigatePeriod("next")}
								>
									<ChevronRight className="w-4 h-4" />
								</Button>
							</div>
						</div>{" "}
						{/* Time Range Tabs */}
						<div className="flex gap-2 border-b">
							<Button
								variant={
									timeRange === "weekly" ? "default" : "ghost"
								}
								onClick={() => handleTimeRangeChange("weekly")}
								className="rounded-b-none"
							>
								Weekly
							</Button>
							<Button
								variant={
									timeRange === "monthly"
										? "default"
										: "ghost"
								}
								onClick={() => handleTimeRangeChange("monthly")}
								className="rounded-b-none"
							>
								Monthly
							</Button>
							<Button
								variant={
									timeRange === "yearly" ? "default" : "ghost"
								}
								onClick={() => handleTimeRangeChange("yearly")}
								className="rounded-b-none"
							>
								Yearly
							</Button>
						</div>
					</div>

					{/* Analytics Cards Section */}
					<AnalyticsCards
						timeRange={timeRange}
						selectedPeriod={selectedPeriod}
					/>

					{/* Spending Trend Chart */}
					<div className="mt-4">
						<SpendingTrendChart
							timeRange={timeRange}
							selectedPeriod={selectedPeriod}
						/>
					</div>
				</div>
			</SidebarInset>
		</SidebarProvider>
	);
}
