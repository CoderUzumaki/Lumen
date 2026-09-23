import { AuthGuard } from "@/components/auth/auth-guard";
import AnalyticsContent from "./analyticsContent";

export default function AnalyticsPage() {
	return (
		<AuthGuard>
			<AnalyticsContent />
		</AuthGuard>
	);
}
