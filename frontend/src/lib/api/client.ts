import axios, { AxiosInstance, AxiosError } from "axios";
import { getSupabaseBrowserClient } from "@/lib/supabase/client";

const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL;
if (!API_BASE_URL) {
	throw new Error(
		"NEXT_PUBLIC_BACKEND_URL is not set. See frontend/.env.example."
	);
}

const TOKEN_KEY = "lumen_access_token";
const USER_KEY = "lumen_user";
const TOKEN_KEY_LEGACY = "invox_access_token";
const USER_KEY_LEGACY = "invox_user";

function migrateLegacyStorage(): void {
	if (typeof window === "undefined") return;
	const legacyToken = localStorage.getItem(TOKEN_KEY_LEGACY);
	if (legacyToken && !localStorage.getItem(TOKEN_KEY)) {
		localStorage.setItem(TOKEN_KEY, legacyToken);
		localStorage.removeItem(TOKEN_KEY_LEGACY);
	}
	const legacyUser = localStorage.getItem(USER_KEY_LEGACY);
	if (legacyUser && !localStorage.getItem(USER_KEY)) {
		localStorage.setItem(USER_KEY, legacyUser);
		localStorage.removeItem(USER_KEY_LEGACY);
	}
}

export const tokenManager = {
	getToken: (): string | null => {
		if (typeof window === "undefined") return null;
		migrateLegacyStorage();
		return localStorage.getItem(TOKEN_KEY);
	},

	setToken: (token: string): void => {
		if (typeof window === "undefined") return;
		localStorage.setItem(TOKEN_KEY, token);
		document.cookie = "lumen_session=1; path=/; max-age=604800; samesite=lax";
	},

	removeToken: (): void => {
		if (typeof window === "undefined") return;
		localStorage.removeItem(TOKEN_KEY);
		localStorage.removeItem(USER_KEY);
		localStorage.removeItem(TOKEN_KEY_LEGACY);
		localStorage.removeItem(USER_KEY_LEGACY);
		document.cookie = "lumen_session=; path=/; max-age=0; samesite=lax";
	},

	getUser: (): Record<string, unknown> | null => {
		if (typeof window === "undefined") return null;
		migrateLegacyStorage();
		const userStr = localStorage.getItem(USER_KEY);
		return userStr ? JSON.parse(userStr) : null;
	},

	setUser: (user: Record<string, unknown>): void => {
		if (typeof window === "undefined") return;
		localStorage.setItem(USER_KEY, JSON.stringify(user));
	},
};

const createApiClient = (): AxiosInstance => {
	const client = axios.create({
		baseURL: API_BASE_URL,
		headers: { "Content-Type": "application/json" },
		withCredentials: false,
	});

	client.interceptors.request.use(
		(config) => {
			const token = tokenManager.getToken();
			if (token) {
				config.headers.Authorization = `Bearer ${token}`;
			}
			return config;
		},
		(error) => Promise.reject(error)
	);

	client.interceptors.response.use(
		(response) => response,
		(error: AxiosError) => {
			if (error.response?.status === 401) {
				tokenManager.removeToken();
				if (typeof window !== "undefined") {
					const next =
						window.location.pathname + window.location.search;
					window.location.href = `/signin?reason=expired&next=${encodeURIComponent(
						next
					)}`;
				}
			}
			return Promise.reject(error);
		}
	);

	return client;
};

export const apiClient = createApiClient();

export const authApi = {
	getCurrentUser: async () => {
		const response = await apiClient.get("/api/v1/auth/me");
		return response.data;
	},

	logout: async (): Promise<void> => {
		const supabase = getSupabaseBrowserClient();
		await supabase.auth.signOut();
		tokenManager.removeToken();
		if (typeof window !== "undefined") {
			window.location.href = "/";
		}
	},
};

export const invoiceApi = {
	getMyInvoices: async (page = 1, pageSize = 100) => {
		const response = await apiClient.get("/api/v1/invoices/", {
			params: { page, page_size: pageSize },
		});
		return response.data;
	},

	uploadInvoice: async (file: File) => {
		const formData = new FormData();
		formData.append("file", file);
		const response = await apiClient.post("/extract", formData, {
			headers: { "Content-Type": "multipart/form-data" },
		});
		return response.data;
	},

	getInvoiceStats: async () => {
		const response = await apiClient.get("/api/v1/invoices/stats");
		return response.data;
	},

	getInvoice: async (invoiceId: string) => {
		const response = await apiClient.get(`/api/v1/invoices/${invoiceId}`);
		return response.data;
	},

	updateInvoice: async (
		invoiceId: string,
		data: { status?: string; [key: string]: unknown }
	) => {
		const response = await apiClient.put(
			`/api/v1/invoices/${invoiceId}`,
			data
		);
		return response.data;
	},

	deleteInvoice: async (invoiceId: string) => {
		await apiClient.delete(`/api/v1/invoices/${invoiceId}`);
	},

	exportInvoices: async (params: {
		format: "csv" | "json";
		status?: string;
		start_date?: string;
		end_date?: string;
		min_amount?: number;
		max_amount?: number;
		vendor_name?: string;
	}) => {
		const queryParams = new URLSearchParams();
		queryParams.append("format", params.format);
		if (params.status) queryParams.append("status", params.status);
		if (params.start_date)
			queryParams.append("start_date", params.start_date);
		if (params.end_date) queryParams.append("end_date", params.end_date);
		if (params.min_amount !== undefined)
			queryParams.append("min_amount", params.min_amount.toString());
		if (params.max_amount !== undefined)
			queryParams.append("max_amount", params.max_amount.toString());
		if (params.vendor_name)
			queryParams.append("vendor_name", params.vendor_name);

		const response = await apiClient.get(
			`/api/v1/invoices/export?${queryParams.toString()}`,
			{ responseType: "blob" }
		);

		const url = window.URL.createObjectURL(new Blob([response.data]));
		const link = document.createElement("a");
		link.href = url;
		let filename = `invoices_export.${params.format}`;
		const contentDisposition = response.headers["content-disposition"];
		if (contentDisposition) {
			const filenameMatch =
				contentDisposition.match(/filename="?(.+)"?/i);
			if (filenameMatch) filename = filenameMatch[1];
		}
		link.setAttribute("download", filename);
		document.body.appendChild(link);
		link.click();
		link.remove();
		window.URL.revokeObjectURL(url);
	},

	pollEmails: async () => {
		const response = await apiClient.post("/api/v1/invoices/poll-emails");
		return response.data;
	},
};

/** Email config — identity from JWT; never send user_id from the client. */
export const emailConfigApi = {
	getStatus: async () => {
		const response = await apiClient.get("/api/v1/email-config/status");
		return response.data;
	},

	getConfig: async () => {
		const response = await apiClient.get("/api/v1/email-config");
		return response.data;
	},

	createConfig: async (data: {
		email_address: string;
		provider?: string;
		imap_server: string;
		imap_port: number;
		imap_username?: string;
		imap_password: string;
		use_ssl?: boolean;
		polling_enabled?: boolean;
		polling_interval_minutes?: number;
		folder_to_watch?: string;
		mark_as_read?: boolean;
	}) => {
		const response = await apiClient.post("/api/v1/email-config", data);
		return response.data;
	},

	updateConfig: async (data: {
		polling_enabled?: boolean;
		polling_interval_minutes?: number;
		folder_to_watch?: string;
		mark_as_read?: boolean;
		imap_password?: string;
	}) => {
		const response = await apiClient.put("/api/v1/email-config", data);
		return response.data;
	},

	deleteConfig: async () => {
		await apiClient.delete("/api/v1/email-config");
	},

	testConnection: async () => {
		const response = await apiClient.post("/api/v1/email-config/test");
		return response.data;
	},

	pollNow: async () => {
		const response = await apiClient.post("/api/v1/email-config/poll-now");
		return response.data;
	},

	pausePolling: async () => {
		const response = await apiClient.post("/api/v1/email-config/pause");
		return response.data;
	},

	resumePolling: async () => {
		const response = await apiClient.post("/api/v1/email-config/resume");
		return response.data;
	},

	getLogs: async (limit = 50) => {
		const response = await apiClient.get(
			`/api/v1/email-config/logs?limit=${limit}`
		);
		return response.data;
	},

	getGmailAuthUrl: async () => {
		const response = await apiClient.get(
			"/api/v1/email-config/gmail/auth-url"
		);
		return response.data;
	},

	gmailCallback: async (code: string, state: string) => {
		const response = await apiClient.post(
			"/api/v1/email-config/gmail/callback",
			{ code, state }
		);
		return response.data;
	},

	disconnectGmail: async () => {
		const response = await apiClient.post(
			"/api/v1/email-config/gmail/disconnect"
		);
		return response.data;
	},
};

export const ocrApi = {
	extractInvoice: async (file: File) => {
		const formData = new FormData();
		formData.append("file", file);
		const response = await apiClient.post("/extract", formData, {
			headers: { "Content-Type": "multipart/form-data" },
		});
		return response.data;
	},

	extractBatch: async (file: File) => {
		const formData = new FormData();
		formData.append("file", file);
		const response = await apiClient.post("/extract-batch", formData, {
			headers: { "Content-Type": "multipart/form-data" },
		});
		return response.data;
	},
};

export const chatApi = {
	sendMessage: async (query: string) => {
		const response = await apiClient.post("/chat", { query });
		return response.data;
	},

	getSuggestions: async () => {
		const response = await apiClient.get("/chat/suggestions");
		return response.data;
	},

	getHistory: async (limit = 50) => {
		const response = await apiClient.get("/chat/history", {
			params: { limit },
		});
		return response.data;
	},

	clearHistory: async () => {
		const response = await apiClient.delete("/chat/history");
		return response.data;
	},
};

/** Analytics — backend derives user from JWT. */
export const analyticsApi = {
	getTimeRangeAnalytics: async (
		timeRange: "weekly" | "monthly" | "yearly",
		year: number,
		month?: number,
		week?: number
	) => {
		const queryParams = new URLSearchParams();
		queryParams.append("time_range", timeRange);
		queryParams.append("year", year.toString());
		if (month !== undefined) queryParams.append("month", month.toString());
		if (week !== undefined) queryParams.append("week", week.toString());
		const response = await apiClient.get(
			`/analytics/summary?${queryParams.toString()}`
		);
		return response.data;
	},

	getAllTimeSummary: async () => {
		const response = await apiClient.get("/analytics/summary");
		return response.data;
	},
};

export const transactionApi = {
	getTransactions: async (params?: {
		page?: number;
		page_size?: number;
		date_from?: string;
		date_to?: string;
		category?: string;
		vendor?: string;
		min_amount?: number;
		max_amount?: number;
		sort_by?: string;
		sort_order?: "asc" | "desc";
	}) => {
		const queryParams = new URLSearchParams();
		if (params?.page) queryParams.append("page", params.page.toString());
		if (params?.page_size)
			queryParams.append("page_size", params.page_size.toString());
		if (params?.date_from)
			queryParams.append("date_from", params.date_from);
		if (params?.date_to) queryParams.append("date_to", params.date_to);
		if (params?.category) queryParams.append("category", params.category);
		if (params?.vendor) queryParams.append("vendor", params.vendor);
		if (params?.min_amount)
			queryParams.append("min_amount", params.min_amount.toString());
		if (params?.max_amount)
			queryParams.append("max_amount", params.max_amount.toString());
		if (params?.sort_by) queryParams.append("sort_by", params.sort_by);
		if (params?.sort_order)
			queryParams.append("sort_order", params.sort_order);

		const response = await apiClient.get(
			`/transactions?${queryParams.toString()}`
		);
		return response.data;
	},

	updateTransaction: async (
		transactionId: string,
		data: {
			vendor_name?: string;
			invoice_number?: string;
			date?: string;
			total_amount?: number;
			tax_amount?: number;
			payment_method?: string;
			address?: string;
			category?: string;
			items?: Array<{
				item_name: string;
				quantity: number;
				unit_price: number;
				total_price: number;
			}>;
		}
	) => {
		const response = await apiClient.put(
			`/transactions/${transactionId}`,
			data
		);
		return response.data;
	},

	createTransaction: async (data: {
		vendor_name: string;
		invoice_number?: string;
		date?: string;
		total_amount?: number;
		tax_amount?: number;
		payment_method?: string;
		address?: string;
		category?: string;
		items?: Array<{
			item_name: string;
			quantity: number;
			unit_price: number;
			total_price: number;
		}>;
	}) => {
		const response = await apiClient.post("/transactions", data);
		return response.data;
	},

	deleteTransaction: async (transactionId: string) => {
		const response = await apiClient.delete(
			`/transactions/${transactionId}`
		);
		return response.data;
	},
};

export const aiAnalyticsApi = {
	getDashboard: async () => {
		const response = await apiClient.get("/api/analytics/dashboard");
		return response.data;
	},

	runAnalysis: async (
		options: {
			includeFraud?: boolean;
			includeForecast?: boolean;
			includeRisk?: boolean;
			useLlm?: boolean;
		} = {}
	) => {
		const response = await apiClient.post("/api/analytics/analyze", {
			include_fraud: options.includeFraud ?? true,
			include_forecast: options.includeForecast ?? true,
			include_risk: options.includeRisk ?? true,
			use_llm: options.useLlm ?? false,
		});
		return response.data;
	},

	getReminders: async (daysAhead: number = 7) => {
		const response = await apiClient.get("/api/analytics/reminders", {
			params: { days_ahead: daysAhead },
		});
		return response.data;
	},

	getAnomalies: async (riskLevel?: string) => {
		const response = await apiClient.get("/api/analytics/anomalies", {
			params: riskLevel ? { risk_level: riskLevel } : {},
		});
		return response.data;
	},

	getForecast: async (daysAhead: number = 30) => {
		const response = await apiClient.get("/api/analytics/forecast", {
			params: { days_ahead: daysAhead },
		});
		return response.data;
	},

	getRiskScore: async () => {
		const response = await apiClient.get("/api/analytics/risk-score");
		return response.data;
	},

	getInsights: async (options: {
		type?: string;
		severity?: string;
		limit?: number;
	} = {}) => {
		const response = await apiClient.get("/api/analytics/insights", {
			params: {
				...(options.type && { type: options.type }),
				...(options.severity && { severity: options.severity }),
				limit: options.limit || 20,
			},
		});
		return response.data;
	},

	markInsightRead: async (insightId: number) => {
		const response = await apiClient.post(
			`/api/analytics/insights/${insightId}/read`
		);
		return response.data;
	},

	getPatterns: async (patternType?: string) => {
		const response = await apiClient.get("/api/analytics/patterns", {
			params: patternType ? { pattern_type: patternType } : {},
		});
		return response.data;
	},

	healthCheck: async () => {
		const response = await apiClient.get("/api/analytics/health");
		return response.data;
	},
};

export const isAuthenticated = (): boolean => {
	return tokenManager.getToken() !== null;
};
