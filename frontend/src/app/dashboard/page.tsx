"use client";

import dynamic from "next/dynamic";
import { AuthGuard } from "@/components/auth/auth-guard";

// Dynamically import the DashboardContent with ssr disabled
const DashboardContent = dynamic(() => import("./dashboardContent"), {
  ssr: false,
});

export default function DashboardPage() {
  return (
    <AuthGuard>
      <DashboardContent />
    </AuthGuard>
  );
}