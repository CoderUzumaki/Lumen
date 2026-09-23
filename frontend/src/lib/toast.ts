type ToastType = "success" | "error" | "info";

function showToast(message: string, type: ToastType = "info") {
	if (typeof document === "undefined") return;

	const root = document.getElementById("lumen-toast-root");
	const container =
		root ??
		(() => {
			const el = document.createElement("div");
			el.id = "lumen-toast-root";
			el.className =
				"fixed bottom-4 right-4 z-[9999] flex flex-col gap-2 pointer-events-none";
			document.body.appendChild(el);
			return el;
		})();

	const toast = document.createElement("div");
	const colors =
		type === "error"
			? "bg-red-600 text-white"
			: type === "success"
				? "bg-emerald-600 text-white"
				: "bg-gray-900 text-white";
	toast.className = `pointer-events-auto px-4 py-3 rounded-lg shadow-lg text-sm max-w-sm ${colors}`;
	toast.textContent = message;
	container.appendChild(toast);

	window.setTimeout(() => {
		toast.remove();
	}, 4000);
}

export const toast = {
	success: (message: string) => showToast(message, "success"),
	error: (message: string) => showToast(message, "error"),
	info: (message: string) => showToast(message, "info"),
};
