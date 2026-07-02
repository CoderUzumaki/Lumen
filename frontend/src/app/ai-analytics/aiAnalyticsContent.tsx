"use client";

import { SidebarProvider } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/app-sidebar";
import { useState, useEffect } from "react";
import QuickStatsCard from "@/components/ai-analytics/quickStatsCard";
import PaymentCalendarCard from "@/components/ai-analytics/paymentCalendarCard";
import ReminderDetailsCard from "@/components/ai-analytics/reminderDetailsCard";
import AnomalyDetectionCard from "@/components/ai-analytics/anomalyDetectionCard";
import AISuggestionsCard from "@/components/ai-analytics/aiSuggestionsCard";
import SpendingTrendGraph from "@/components/ai-analytics/spendingTrendGraph";
import CategoryPieChart from "@/components/ai-analytics/categoryPieChart";
import { aiAnalyticsApi } from "@/lib/api/client";

import { logger } from "@/lib/logger";

export default function AIAnalyticsContent() {
	const [analysisTriggered, setAnalysisTriggered] = useState(false);

	useEffect(() => {
		const triggerAnalysis = async () => {
			if (analysisTriggered) return;

			try {
				logger.debug("Triggering AI analysis...");
				const data = await aiAnalyticsApi.runAnalysis({
					includeFraud: true,
					includeForecast: true,
					includeRisk: true,
					useLlm: false,
				});
				logger.debug("AI Analysis complete:", data);
				setAnalysisTriggered(true);
			} catch (error) {
				console.error("Error triggering analysis:", error);
			}
		};

		void triggerAnalysis();
	}, [analysisTriggered]);

	return (
		<SidebarProvider>
			<AppSidebar />
			<main className="flex-1 overflow-y-auto bg-gray-50">
				<div className="container mx-auto p-4 md:p-6 lg:p-8">
					<div className="mb-6">
						<h1 className="text-3xl font-bold text-gray-900 mb-2">
							AI Analytics
							{!analysisTriggered && (
								<span className="ml-3 text-sm text-blue-600 animate-pulse">
									Analyzing...
								</span>
							)}
						</h1>
						<p className="text-gray-600">
							Intelligent insights and predictions for your
							financial data
						</p>
					</div>

					<div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
						<QuickStatsCard />
						<PaymentCalendarCard />
						<ReminderDetailsCard />
						<AnomalyDetectionCard />
						<div className="lg:col-span-2">
							<AISuggestionsCard />
						</div>
					</div>

					<div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-6">
						<div className="lg:col-span-2">
							<SpendingTrendGraph />
						</div>
						<div className="lg:col-span-1">
							<CategoryPieChart />
						</div>
					</div>
				</div>
			</main>
		</SidebarProvider>
	);
}
