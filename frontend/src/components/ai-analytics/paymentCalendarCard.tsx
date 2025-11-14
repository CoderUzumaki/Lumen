"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
	Calendar as CalendarIcon,
	ChevronLeft,
	ChevronRight,
} from "lucide-react";
import { motion } from "framer-motion";
import { useState } from "react";

// Mock data - Replace with API call
const mockPaymentDates = {
	upcoming: [18, 22, 28], // Dates with upcoming payments
	forecast: [15, 20, 25, 30], // Dates with AI forecasted payments
};

const cardVariants = {
	hidden: { opacity: 0, y: 20 },
	visible: {
		opacity: 1,
		y: 0,
		transition: {
			duration: 0.5,
			ease: "easeOut",
			delay: 0.1,
		},
	},
};

export default function PaymentCalendarCard() {
	const [currentDate, setCurrentDate] = useState(new Date());

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

	const isUpcoming = (day: number) => mockPaymentDates.upcoming.includes(day);
	const isForecast = (day: number) => mockPaymentDates.forecast.includes(day);

	return (
		<motion.div variants={cardVariants} initial="hidden" animate="visible">
			<Card className="border-slate-800 shadow-lg hover:shadow-xl transition-all duration-300 bg-slate-900/50 backdrop-blur-sm">
				<CardHeader className="pb-3">
					<CardTitle className="text-lg font-semibold text-white flex items-center justify-between">
						<div className="flex items-center gap-2">
							<CalendarIcon className="w-5 h-5 text-purple-400" />
							Payment Calendar
						</div>
						<div className="flex items-center gap-2">
							<button
								onClick={previousMonth}
								className="p-1 hover:bg-slate-700 rounded-lg transition-colors"
								aria-label="Previous month"
							>
								<ChevronLeft className="w-4 h-4 text-slate-300" />
							</button>
							<button
								onClick={nextMonth}
								className="p-1 hover:bg-slate-700 rounded-lg transition-colors"
								aria-label="Next month"
							>
								<ChevronRight className="w-4 h-4 text-slate-300" />
							</button>
						</div>
					</CardTitle>
				</CardHeader>
				<CardContent>
					<div className="space-y-3">
						{/* Month/Year */}
						<p className="text-sm font-medium text-slate-200 text-center">
							{monthName}
						</p>

						{/* Calendar Grid */}
						<div className="grid grid-cols-7 gap-1">
							{/* Day Headers */}
							{["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"].map(
								(day) => (
									<div
										key={day}
										className="text-center text-xs font-medium text-slate-400 py-1"
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
													: "text-slate-300 hover:bg-slate-700"
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
								<span className="text-slate-300">Upcoming</span>
							</div>
							<div className="flex items-center gap-1.5">
								<div className="w-3 h-3 rounded bg-blue-500"></div>
								<span className="text-slate-300">Forecast</span>
							</div>
						</div>
					</div>
				</CardContent>
			</Card>
		</motion.div>
	);
}
