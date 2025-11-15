"use client";

import { useState, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { X, Upload, CheckCircle, AlertCircle } from "lucide-react";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { DialogTitle } from "@radix-ui/react-dialog";
import { ocrApi } from "@/lib/api/client";
import { eventBus, EVENTS } from "@/lib/events";

interface FileWithStatus {
	file: File;
	status: "pending" | "uploading" | "success" | "error";
	error?: string;
	extractedData?: any;
}

export function DialogDemo() {
	const [files, setFiles] = useState<FileWithStatus[]>([]);
	const [uploading, setUploading] = useState(false);
	const [open, setOpen] = useState(false);

	const onFiles = useCallback((selected: FileList | null) => {
		if (!selected) return;
		const newFiles = Array.from(selected).map((file) => ({
			file,
			status: "pending" as const,
		}));
		setFiles((prev) => [...prev, ...newFiles]);
	}, []);

	const handleDrop = useCallback(
		(e: React.DragEvent) => {
			e.preventDefault();
			onFiles(e.dataTransfer.files);
		},
		[onFiles]
	);

	const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
		onFiles(e.target.files);
		e.currentTarget.value = ""; // reset
	};

	const removeFile = (idx: number) =>
		setFiles((prev) => prev.filter((_, i) => i !== idx));

	const handleUpload = async () => {
		if (files.length === 0) return;

		setUploading(true);

		for (let i = 0; i < files.length; i++) {
			const fileItem = files[i];

			if (fileItem.status !== "pending") continue;

			// Update status to uploading
			setFiles((prev) => {
				const updated = [...prev];
				updated[i] = { ...updated[i], status: "uploading" };
				return updated;
			});

			try {
				console.log("📤 Uploading file:", fileItem.file.name);
				// Use OCR API to extract data - this saves to database automatically
				const result = await ocrApi.extractInvoice(
					fileItem.file,
					"123"
				);

				console.log("📥 OCR API Response:", result);

				if (result.success && result.data) {
					console.log(
						"✅ Invoice extracted and saved to database:",
						result.data
					);
					console.log("📢 Emitting INVOICE_UPDATED event...");

					// Emit event to trigger refresh in other components
					eventBus.emit(EVENTS.INVOICE_UPDATED);

					console.log("✅ Event emitted successfully");
				} else {
					console.warn(
						"⚠️ Upload succeeded but no data or success=false",
						result
					);
				}

				// Update status to success
				setFiles((prev) => {
					const updated = [...prev];
					updated[i] = {
						...updated[i],
						status: "success",
						extractedData: result.data,
					};
					return updated;
				});
			} catch (error) {
				console.error("Upload error:", error);

				const errorMessage =
					error instanceof Error ? error.message : "Upload failed";

				// Update status to error
				setFiles((prev) => {
					const updated = [...prev];
					updated[i] = {
						...updated[i],
						status: "error",
						error: errorMessage,
					};
					return updated;
				});
			}
		}

		setUploading(false);

		// Check if all files were successful
		const allSuccess = files.every((f) => f.status === "success");
		if (allSuccess) {
			console.log("✅ All uploads successful! Closing dialog in 1.5s...");
			// Close dialog after a short delay and emit final event
			setTimeout(() => {
				console.log(
					"📢 Emitting final INVOICE_UPDATED event before closing dialog"
				);
				setOpen(false);
				setFiles([]);
				// Emit one final event to ensure all components refresh
				eventBus.emit(EVENTS.INVOICE_UPDATED);
			}, 1500);
		} else {
			console.warn(
				"⚠️ Some uploads failed",
				files.filter((f) => f.status !== "success")
			);
		}
	};

	const getStatusIcon = (status: FileWithStatus["status"]) => {
		switch (status) {
			case "uploading":
				return (
					<div className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary"></div>
				);
			case "success":
				return <CheckCircle className="w-4 h-4 text-green-500" />;
			case "error":
				return <AlertCircle className="w-4 h-4 text-red-500" />;
			default:
				return null;
		}
	};

	return (
		<Dialog open={open} onOpenChange={setOpen}>
			<DialogTrigger asChild>
				<Button>Upload Documents</Button>
			</DialogTrigger>
			<DialogContent className="max-w-3xl bg-linear-to-b from-[#0b0612] to-[#05020a] border-neutral-800">
				<DialogTitle className="hidden"></DialogTitle>
				<div className="flex items-start justify-between gap-4">
					<div className="flex items-center gap-3">
						<div className="p-2 rounded-xl bg-neutral-800/50">
							<Upload className="w-5 h-5 text-neutral-300" />
						</div>
						<div>
							<h3 className="text-white text-2xl font-semibold">
								Upload documents
							</h3>
							<p className="text-sm text-neutral-300 mt-1">
								Drag & drop files here or click to browse.
								Supported: PDF, PNG, JPG
							</p>
						</div>
					</div>

					<button
						onClick={() => setOpen(false)}
						className="p-2 rounded-lg hover:bg-neutral-800/50 transition-colors"
					>
						<X className="w-5 h-5 text-neutral-400 hover:text-white" />
					</button>
				</div>

				<div
					onDragOver={(e) => e.preventDefault()}
					onDrop={handleDrop}
					className="mt-6 rounded-xl border-2 border-dashed border-neutral-700 p-6 flex flex-col items-center justify-center text-center bg-transparent"
				>
					<input
						id="file-input-dashboard"
						type="file"
						multiple
						accept=".pdf,.png,.jpg,.jpeg"
						onChange={handleFileChange}
						className="hidden"
					/>
					<label
						htmlFor="file-input-dashboard"
						className="cursor-pointer w-full"
					>
						<div className="text-white text-lg font-medium mb-2">
							Drop files here
						</div>
						<div className="text-neutral-400 mb-4">
							or click to select files
						</div>
						<div className="flex gap-3 justify-center">
							<Button asChild type="button">
								<span className="px-4 py-2">Browse</span>
							</Button>
							<Button
								variant="secondary"
								onClick={handleUpload}
								disabled={uploading || files.length === 0}
								type="button"
							>
								{uploading ? "Uploading..." : "Upload"}
							</Button>
						</div>
					</label>
				</div>

				<div className="mt-6">
					<h4 className="text-white text-sm font-medium mb-2">
						Files
					</h4>
					<div className="flex flex-col gap-2 max-h-48 overflow-auto">
						{files.length === 0 && (
							<div className="text-neutral-500 text-sm">
								No files selected
							</div>
						)}
						{files.map((fileItem, i) => (
							<div
								key={i}
								className="flex items-center justify-between gap-4 bg-neutral-900/50 p-2 rounded-md"
							>
								<div className="flex items-center gap-2 flex-1 min-w-0">
									{getStatusIcon(fileItem.status)}
									<div className="truncate text-sm text-white">
										{fileItem.file.name}
									</div>
								</div>
								<div className="flex items-center gap-2">
									<div className="text-xs text-neutral-400">
										{(fileItem.file.size / 1024).toFixed(1)}{" "}
										KB
									</div>
									{fileItem.status === "error" &&
										fileItem.error && (
											<div className="text-xs text-red-400 max-w-[150px] truncate">
												{fileItem.error}
											</div>
										)}
									<Button
										variant="ghost"
										size="sm"
										onClick={() => removeFile(i)}
										disabled={
											fileItem.status === "uploading"
										}
									>
										Remove
									</Button>
								</div>
							</div>
						))}
					</div>
				</div>
			</DialogContent>
		</Dialog>
	);
}
