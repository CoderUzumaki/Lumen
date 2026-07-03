"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
	Calendar as CalendarIcon,
	ChevronLeft,
	ChevronRight,
} from "lucide-react";
import { motion } from "framer-motion";
import { useState, useEffect } from "react";
import { analyticsApi } from "@/lib/api/client";

const cardVariants = {
	hidden: { opacity: 0, y: 20 },
	visible: {
		opacity: 1,
		y: 0,
		transition: {
			duration: 0.5,
			ease: [0.4, 0, 0.2, 1] as any,
			delay: 0.1,
		},
	},
};

export default function PaymentCalendarCard() {
	const [currentDate, setCurrentDate] = useState(new Date());
	const [paymentDates, setPaymentDates] = useState<{
		upcoming: number[];
		forecast: number[];
	}>({
		upcoming: [],
		forecast: [],
	});
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		const fetchPaymentDates = async () => {
			try {
				setError(null);
				const response = await analyticsApi.getAllTimeSummary();
				if (response.success && response.payment_calendar) {
					setPaymentDates(response.payment_calendar);
				} else {
					setPaymentDates({ upcoming: [], forecast: [] });
					setError("Could not load payment calendar.");
				}
			} catch (err) {
				console.error("Failed to load payment calendar", err);
				setPaymentDates({ upcoming: [], forecast: [] });
				setError("Could not load payment calendar.");
			} finally {
				setLoading(false);
			}
		};
		fetchPaymentDates();
	}, [currentDate]);

	const getDaysInMonth = (date: Date) => {
		const year = date.getFullYear();
		const month = date.getMonth();
		const firstDay = new Date(year, month, 1).getDay();
		const daysInMonth = new Date(year, month + 1, 0).getDate();
		return { firstDay, daysInMonth };
	};

	const { firstDay, daysInMonth } = getDaysInMonth(currentDate);
	const monthName = currentDate.toLocaleDateString("en-US", {
		month: "long",
		year: "numeric",
	});

	const previousMonth = () => {
		setCurrentDate(
			new Date(currentDate.getFullYear(), currentDate.getMonth() - 1)
		);
	};

	const nextMonth = () => {
		setCurrentDate(
			new Date(currentDate.getFullYear(), currentDate.getMonth() + 1)
		);
	};

	const isUpcoming = (day: number) => paymentDates.upcoming.includes(day);
	const isForecast = (day: number) => paymentDates.forecast.includes(day);

	if (loading) {
		return (
			<Card className="border-border/70 bg-card/80 shadow-lg shadow-black/10">
				<CardContent className="flex items-center justify-center h-[280px]">
					<p className="text-muted-foreground">Loading calendar...</p>
				</CardContent>
			</Card>
		);
	}

	if (error) {
		return (
			<Card className="border-border/70 bg-card/80 shadow-lg shadow-black/10">
				<CardContent className="flex items-center justify-center h-[280px]">
					<p className="text-muted-foreground">{error}</p>
				</CardContent>
			</Card>
		);
	}

	return (
		<motion.div variants={cardVariants} initial="hidden" animate="visible">
			<Card className="border-border/70 bg-card/80 shadow-lg shadow-black/10 transition-all duration-300 hover:shadow-xl hover:shadow-black/10">
				<CardHeader className="pb-3">
					<CardTitle className="flex items-center justify-between text-lg font-semibold text-foreground">
						<div className="flex items-center gap-2">
							<CalendarIcon className="h-5 w-5 text-primary" />
							Payment Calendar
						</div>
						<div className="flex items-center gap-2">
							<button
								onClick={previousMonth}
								className="rounded-lg p-1 transition-colors hover:bg-accent"
								aria-label="Previous month"
							>
								<ChevronLeft className="h-4 w-4 text-muted-foreground" />
							</button>
							<button
								onClick={nextMonth}
								className="rounded-lg p-1 transition-colors hover:bg-accent"
								aria-label="Next month"
							>
								<ChevronRight className="h-4 w-4 text-muted-foreground" />
							</button>
						</div>
					</CardTitle>
				</CardHeader>
				<CardContent>
					<div className="space-y-3">
						{/* Month/Year */}
						<p className="text-center text-sm font-medium text-foreground">
							{monthName}
						</p>

						{/* Calendar Grid */}
						<div className="grid grid-cols-7 gap-1">
							{/* Day Headers */}
							{["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"].map(
								(day) => (
									<div
										key={day}
										className="py-1 text-center text-xs font-medium text-muted-foreground"
									>
										{day}
									</div>
								)
							)}

							{/* Empty cells for days before month starts */}
							{Array.from({ length: firstDay }).map(
								(_, index) => (
									<div
										key={`empty-${index}`}
										className="aspect-square"
									></div>
								)
							)}

							{/* Days of the month */}
							{Array.from({ length: daysInMonth }).map(
								(_, index) => {
									const day = index + 1;
									const isUpcomingDay = isUpcoming(day);
									const isForecastDay = isForecast(day);

									return (
										<div
											key={day}
											className={`aspect-square flex items-center justify-center text-sm rounded-lg cursor-pointer transition-all duration-200 ${
												isUpcomingDay
													? "bg-amber-500/80 text-white font-semibold hover:bg-amber-500"
													: isForecastDay
													? "bg-primary/80 text-white font-semibold hover:bg-primary"
													: "text-foreground hover:bg-accent"
											}`}
										>
											{day}
										</div>
									);
								}
							)}
						</div>

						{/* Legend */}
						<div className="flex items-center gap-4 pt-2 text-xs">
							<div className="flex items-center gap-1.5">
								<div className="h-3 w-3 rounded bg-amber-500"></div>
								<span className="text-muted-foreground">Upcoming</span>
							</div>
							<div className="flex items-center gap-1.5">
								<div className="h-3 w-3 rounded bg-primary"></div>
								<span className="text-muted-foreground">Forecast</span>
							</div>
						</div>
					</div>
				</CardContent>
			</Card>
		</motion.div>
	);
}
