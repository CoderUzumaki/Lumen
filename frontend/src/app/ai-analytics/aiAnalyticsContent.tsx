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

export default function AIAnalyticsContent() {
	const [analysisTriggered, setAnalysisTriggered] = useState(false);

	useEffect(() => {
		// Trigger AI analysis when page loads
		const triggerAnalysis = async () => {
			if (analysisTriggered) return;

			try {
				console.log("🚀 Triggering AI analysis...");
				const response = await fetch(
					"http://localhost:5000/api/analytics/analyze",
					{
						method: "POST",
						headers: {
							"Content-Type": "application/json",
						},
						body: JSON.stringify({
							user_id: 123,
							include_fraud: true,
							include_forecast: true,
							include_risk: true,
							use_llm: false, // Set to true if you want LLM-based insights
						}),
					}
				);

				if (response.ok) {
					const data = await response.json();
					console.log("✅ AI Analysis complete:", data);
					setAnalysisTriggered(true);
				} else {
					console.error("❌ Analysis failed:", await response.text());
				}
			} catch (error) {
				console.error("❌ Error triggering analysis:", error);
			}
		};

		triggerAnalysis();
	}, [analysisTriggered]);

	return (
		<SidebarProvider>
			<AppSidebar />
			<main className="flex-1 overflow-y-auto bg-gray-50">
				<div className="container mx-auto p-4 md:p-6 lg:p-8">
					{/* Header */}
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

					{/* Grid Layout */}
					<div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
						{/* Row 1 - Quick Stats, Payment Calendar, Reminders */}
						<QuickStatsCard />
						<PaymentCalendarCard />
						<ReminderDetailsCard />

						{/* Row 2 - Anomaly Detection spans 1 col, AI Suggestions spans 2 cols */}
						<AnomalyDetectionCard />
						<div className="lg:col-span-2">
							<AISuggestionsCard />
						</div>
					</div>

					{/* Bottom Row - Graph and Pie Chart */}
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
