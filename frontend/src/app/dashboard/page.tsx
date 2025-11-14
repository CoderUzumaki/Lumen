"use client";

import { useRouter } from "next/navigation";
import dynamic from "next/dynamic";

// Dynamically import the DashboardContent with ssr disabled
const DashboardContent = dynamic(() => import("./dashboardContent"), {
  ssr: false,
});

export default function DashboardPage() {
  const router = useRouter();

  return <DashboardContent />;
}