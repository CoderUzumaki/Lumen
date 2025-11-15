"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
	Calendar as CalendarIcon,
	ChevronLeft,
	ChevronRight,
} from "lucide-react";
import { motion } from "framer-motion";
import { useState, useEffect } from "react";
import { transactionApi, tokenManager } from "@/lib/api/client";

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
	}>({ upcoming: [], forecast: [] });
	const [loading, setLoading] = useState(true);

	useEffect(() => {
		const fetchPaymentDates = async () => {
			try {
				setLoading(true);
				const user = tokenManager.getUser();
				if (!user?.id) return;

				const response = await transactionApi.getTransactions(
					String(user.id),
					{
						page: 1,
						page_size: 1000,
					}
				);

				const transactions = response.data || [];

				// Get days with transactions in current month
				const upcomingDays = new Set<number>();
				transactions.forEach((transaction: any) => {
					const date = new Date(transaction.date);
					if (
						date.getMonth() === currentDate.getMonth() &&
						date.getFullYear() === currentDate.getFullYear()
					) {
						upcomingDays.add(date.getDate());
					}
				});

				// Simple forecast: predict recurring patterns (e.g., similar days of month)
				const forecastDays = new Set<number>();
				upcomingDays.forEach((day) => {
					// Predict next occurrence
					if (day + 7 <= getDaysInMonth(currentDate).daysInMonth) {
						forecastDays.add(day + 7);
					}
				});

				setPaymentDates({
					upcoming: Array.from(upcomingDays),
					forecast: Array.from(forecastDays),
				});
			} catch (error) {
				console.error("Failed to fetch payment dates:", error);
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

	return (
		<motion.div variants={cardVariants} initial="hidden" animate="visible">
			<Card className="bg-white border border-gray-200 shadow-sm hover:shadow-md transition-all duration-300">
				<CardHeader className="pb-3">
					<CardTitle className="text-lg font-semibold text-gray-900 flex items-center justify-between">
						<div className="flex items-center gap-2">
							<CalendarIcon className="w-5 h-5 text-purple-600" />
							Payment Calendar
						</div>
						<div className="flex items-center gap-2">
							<button
								onClick={previousMonth}
								className="p-1 hover:bg-gray-100 rounded-lg transition-colors"
								aria-label="Previous month"
							>
								<ChevronLeft className="w-4 h-4 text-gray-600" />
							</button>
							<button
								onClick={nextMonth}
								className="p-1 hover:bg-gray-100 rounded-lg transition-colors"
								aria-label="Next month"
							>
								<ChevronRight className="w-4 h-4 text-gray-600" />
							</button>
						</div>
					</CardTitle>
				</CardHeader>
				<CardContent>
					<div className="space-y-3">
						{/* Month/Year */}
						<p className="text-sm font-medium text-gray-900 text-center">
							{monthName}
						</p>

						{/* Calendar Grid */}
						<div className="grid grid-cols-7 gap-1">
							{/* Day Headers */}
							{["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"].map(
								(day) => (
									<div
										key={day}
										className="text-center text-xs font-medium text-gray-600 py-1"
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
													? "bg-orange-500 text-white font-semibold hover:bg-orange-600"
													: isForecastDay
													? "bg-blue-500 text-white font-semibold hover:bg-blue-600"
													: "text-gray-700 hover:bg-gray-100"
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
								<div className="w-3 h-3 rounded bg-orange-500"></div>
								<span className="text-gray-700">Upcoming</span>
							</div>
							<div className="flex items-center gap-1.5">
								<div className="w-3 h-3 rounded bg-blue-500"></div>
								<span className="text-gray-700">Forecast</span>
							</div>
						</div>
					</div>
				</CardContent>
			</Card>
		</motion.div>
	);
}
