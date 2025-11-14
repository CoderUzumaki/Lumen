"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
// import { useSession } from "next-auth/react";
// import { tokenManager } from "@/lib/api/client";
import dynamic from "next/dynamic";

// Dynamically import the DashboardContent with ssr disabled
const DashboardContent = dynamic(() => import("./chatbotContent"), {
  ssr: false,
});

export default function DashboardPage() {
  const router = useRouter();
//   const { data: session, status } = useSession();
//   const [isLoading, setIsLoading] = useState(true);

//   useEffect(() => {
//     if (status === "loading") {
//       // Still checking session
//       return;
//     }

//     if (status === "unauthenticated") {
//       // Not signed in, redirect to signin
//       router.push("/signin");
//       return;
//     }

//     if (status === "authenticated" && session) {
//       // Store the backend token in localStorage for API calls
//       const backendToken = (session as any).backendToken;
//       if (backendToken) {
//         tokenManager.setToken(backendToken);
//         tokenManager.setUser({
//           id: (session as any).userId,
//           email: session.user?.email || "",
//           name: session.user?.name || "",
//           image: session.user?.image || "",
//         });
//       }
//       setIsLoading(false);
//     }
//   }, [session, status, router]);

//   if (status === "loading" || isLoading) {
//     return (
//       <div className="flex items-center justify-center min-h-screen">
//         <div className="text-center">
//           <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4"></div>
//           <p className="text-muted-foreground">Loading dashboard...</p>
//         </div>
//       </div>
//     );
//   }

  return <DashboardContent />;
}