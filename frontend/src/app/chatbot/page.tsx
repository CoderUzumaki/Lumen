"use client";

import dynamic from "next/dynamic";
import { AuthGuard } from "@/components/auth/auth-guard";

const ChatbotContent = dynamic(() => import("./chatbotContent"), {
	ssr: false,
});

export default function ChatbotPage() {
	return (
		<AuthGuard>
			<ChatbotContent />
		</AuthGuard>
	);
}