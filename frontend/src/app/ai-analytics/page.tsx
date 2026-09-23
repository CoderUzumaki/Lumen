import { AuthGuard } from "@/components/auth/auth-guard";
import AIAnalyticsContent from "./aiAnalyticsContent";

export default function AIAnalyticsPage() {
	return (
		<AuthGuard>
			<AIAnalyticsContent />
		</AuthGuard>
	);
}
