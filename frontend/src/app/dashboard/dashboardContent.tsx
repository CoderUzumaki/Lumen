"use client";

import { AppSidebar } from "@/components/app-sidebar";
import AnimatedListItemUse from "@/components/animatedListItemUse";
import { SectionCards } from "@/components/section-cards";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
} from "@/components/ui/breadcrumb";
import { Separator } from "@/components/ui/separator";
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { DialogDemo } from "@/components/uploadDialog";
import { ExportDialog } from "@/components/exportDialog";
import { EmailConfigDialog } from "@/components/emailConfigDialog";

export default function DashboardContent() {
  return (
    <>
      <SidebarProvider>
        <AppSidebar />
        <SidebarInset>
          <header className="flex h-16 shrink-0 items-center gap-2 transition-[width,height] ease-linear group-has-data-[collapsible=icon]/sidebar-wrapper:h-12">
            <div className="flex items-center gap-2 px-4">
              <SidebarTrigger className="-ml-1" />
              <Separator
                orientation="vertical"
                className="mr-2 data-[orientation=vertical]:h-4"
              />
              <Breadcrumb>
                <BreadcrumbList>
                  <BreadcrumbItem className="hidden md:block">
                    <BreadcrumbLink href="#">
                      <BreadcrumbPage>Dashboard</BreadcrumbPage>
                    </BreadcrumbLink>
                  </BreadcrumbItem>
                </BreadcrumbList>
              </Breadcrumb>
            </div>
            <div className="absolute top-0 right-0 m-3 flex gap-2">
              <EmailConfigDialog
                onConfigured={() => {
                  // Refresh the page or trigger a reload
                  window.location.reload();
                }}
              />
              <DialogDemo />
            </div>
          </header>
          <div className="flex flex-1 flex-col gap-4 p-4 pt-0">
            <div className="grid auto-rows-min gap-4 md:grid-cols-2 lg:grid-cols-4 mb-4">
              <SectionCards />
            </div>
            {/* <div className="h-[100px] bg-muted rounded-3xl">
                    <FileUploadForm /> 
                </div> */}
            <div className="bg-muted/50 min-h-screen flex-1 rounded-xl md:min-h-min">
              <div className="m-5">
                <div className="flex justify-between items-center mb-4">
                  <h2 className="text-lg font-semibold">Invoice Overview</h2>
                  <ExportDialog />
                </div>
                <div>
                  <AnimatedListItemUse />
                </div>
              </div>
            </div>
          </div>
        </SidebarInset>
      </SidebarProvider>
    </>
  );
}