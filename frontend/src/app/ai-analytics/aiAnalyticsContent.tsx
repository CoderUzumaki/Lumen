"use client";

import { useState, useEffect } from "react";
import { DashboardShell } from "@/components/dashboard-shell";
import QuickStatsCard from "@/components/ai-analytics/quickStatsCard";
import PaymentCalendarCard from "@/components/ai-analytics/paymentCalendarCard";
import ReminderDetailsCard from "@/components/ai-analytics/reminderDetailsCard";
import AnomalyDetectionCard from "@/components/ai-analytics/anomalyDetectionCard";
import AISuggestionsCard from "@/components/ai-analytics/aiSuggestionsCard";
import SpendingTrendGraph from "@/components/ai-analytics/spendingTrendGraph";
import CategoryPieChart from "@/components/ai-analytics/categoryPieChart";
import { aiAnalyticsApi } from "@/lib/api/client";

import { logger } from "@/lib/logger";
import { Badge } from "@/components/ui/badge";

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
		<DashboardShell
			title="AI Analytics"
			description="Surface risk, reminders, anomaly detection, and forward-looking spend signals without leaving the core finance workflow."
			eyebrow="AI Insights"
			actions={
				<Badge
					variant="outline"
					className="rounded-full border-border/70 bg-background/60 px-3 py-1 text-sm text-muted-foreground"
				>
					{analysisTriggered ? "Model refreshed" : "Analyzing live data..."}
				</Badge>
			}
		>
			<div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
				<QuickStatsCard />
				<PaymentCalendarCard />
				<ReminderDetailsCard />
				<AnomalyDetectionCard />
				<div className="lg:col-span-2">
					<AISuggestionsCard />
				</div>
			</div>

			<div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
				<div className="lg:col-span-2">
					<SpendingTrendGraph />
				</div>
				<div className="lg:col-span-1">
					<CategoryPieChart />
				</div>
			</div>
		</DashboardShell>
	);
}
