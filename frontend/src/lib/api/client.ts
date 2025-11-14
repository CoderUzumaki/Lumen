import axios, { AxiosInstance, AxiosError } from "axios";

// Backend API base URL
const API_BASE_URL =
	process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:5000";

// Token storage keys
const TOKEN_KEY = "invox_access_token";
const USER_KEY = "invox_user";

/**
 * Token management utilities
 */
export const tokenManager = {
	getToken: (): string | null => {
		if (typeof window === "undefined") return null;
		return localStorage.getItem(TOKEN_KEY);
	},

	setToken: (token: string): void => {
		if (typeof window === "undefined") return;
		localStorage.setItem(TOKEN_KEY, token);
	},

	removeToken: (): void => {
		if (typeof window === "undefined") return;
		localStorage.removeItem(TOKEN_KEY);
		localStorage.removeItem(USER_KEY);
	},

	getUser: (): Record<string, unknown> | null => {
		if (typeof window === "undefined") return null;
		const userStr = localStorage.getItem(USER_KEY);
		return userStr ? JSON.parse(userStr) : null;
	},

	setUser: (user: Record<string, unknown>): void => {
		if (typeof window === "undefined") return;
		localStorage.setItem(USER_KEY, JSON.stringify(user));
	},
};

/**
 * Create axios instance with authentication
 */
const createApiClient = (): AxiosInstance => {
	const client = axios.create({
		baseURL: API_BASE_URL,
		headers: {
			"Content-Type": "application/json",
		},
		withCredentials: false, // Disabled for simplified OCR-only backend
	});

	// Request interceptor to add auth token
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

	// Response interceptor to handle errors
	client.interceptors.response.use(
		(response) => response,
		(error: AxiosError) => {
			if (error.response?.status === 401) {
				// Unauthorized - clear token and redirect to signin
				tokenManager.removeToken();
				if (typeof window !== "undefined") {
					window.location.href = "/signin";
				}
			}
			return Promise.reject(error);
		}
	);

	return client;
};

// Export singleton instance
export const apiClient = createApiClient();

/**
 * Auth API endpoints
 */
export const authApi = {
	/**
	 * Get Google OAuth URL to redirect user for login
	 */
	getGoogleAuthUrl: (): string => {
		return `${API_BASE_URL}/api/v1/auth/google`;
	},

	/**
	 * Get current user information
	 */
	getCurrentUser: async () => {
		const response = await apiClient.get("/api/v1/auth/me");
		return response.data;
	},

	/**
	 * Logout user - clear local storage
	 */
	logout: (): void => {
		tokenManager.removeToken();
		if (typeof window !== "undefined") {
			window.location.href = "/";
		}
	},
};

/**
 * Invoice API endpoints
 */
export const invoiceApi = {
	/**
	 * Get all invoices for the current user (paginated)
	 */
	getMyInvoices: async (page = 1, pageSize = 100) => {
		const response = await apiClient.get("/api/v1/invoices/", {
			params: { page, page_size: pageSize },
		});
		return response.data;
	},

	/**
	 * Upload a PDF/image invoice
	 */
	uploadInvoice: async (file: File) => {
		const formData = new FormData();
		formData.append("file", file);

		const response = await apiClient.post("/extract", formData, {
			headers: {
				"Content-Type": "multipart/form-data",
			},
		});
		return response.data;
	},

	/**
	 * Get invoice statistics
	 */
	getInvoiceStats: async () => {
		const response = await apiClient.get("/api/v1/invoices/stats");
		return response.data;
	},

	/**
	 * Get a specific invoice by ID
	 */
	getInvoice: async (invoiceId: string) => {
		const response = await apiClient.get(`/api/v1/invoices/${invoiceId}`);
		return response.data;
	},

	/**
	 * Update an invoice
	 */
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

	/**
	 * Delete an invoice
	 */
	deleteInvoice: async (invoiceId: string) => {
		await apiClient.delete(`/api/v1/invoices/${invoiceId}`);
	},

	/**
	 * Export invoices with optional filters
	 */
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
			{
				responseType: "blob",
			}
		);

		// Create download link
		const url = window.URL.createObjectURL(new Blob([response.data]));
		const link = document.createElement("a");
		link.href = url;

		// Extract filename from content-disposition header or create default
		const contentDisposition = response.headers["content-disposition"];
		let filename = `invoices_export.${params.format}`;
		if (contentDisposition) {
			const filenameMatch =
				contentDisposition.match(/filename="?(.+)"?/i);
			if (filenameMatch) {
				filename = filenameMatch[1];
			}
		}

		link.setAttribute("download", filename);
		document.body.appendChild(link);
		link.click();
		link.remove();
		window.URL.revokeObjectURL(url);
	},

	/**
	 * Manually poll emails for new invoices (DEPRECATED - use emailConfigApi.pollNow)
	 */
	pollEmails: async () => {
		const response = await apiClient.post("/api/v1/invoices/poll-emails");
		return response.data;
	},
};

/**
 * Email Configuration API endpoints
 */
export const emailConfigApi = {
	/**
	 * Get email configuration status
	 */
	getStatus: async () => {
		const response = await apiClient.get("/api/v1/email-config/status");
		return response.data;
	},

	/**
	 * Get email configuration
	 */
	getConfig: async () => {
		const response = await apiClient.get("/api/v1/email-config");
		return response.data;
	},

	/**
	 * Create email configuration
	 */
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

	/**
	 * Update email configuration
	 */
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

	/**
	 * Delete email configuration
	 */
	deleteConfig: async () => {
		await apiClient.delete("/api/v1/email-config");
	},

	/**
	 * Test IMAP connection
	 */
	testConnection: async () => {
		const response = await apiClient.post("/api/v1/email-config/test");
		return response.data;
	},

	/**
	 * Manually trigger email polling
	 */
	pollNow: async () => {
		const response = await apiClient.post("/api/v1/email-config/poll-now");
		return response.data;
	},

	/**
	 * Pause automatic email polling
	 */
	pausePolling: async () => {
		const response = await apiClient.post("/api/v1/email-config/pause");
		return response.data;
	},

	/**
	 * Resume automatic email polling
	 */
	resumePolling: async () => {
		const response = await apiClient.post("/api/v1/email-config/resume");
		return response.data;
	},

	/**
	 * Get processing logs
	 */
	getLogs: async (limit = 50) => {
		const response = await apiClient.get(
			`/api/v1/email-config/logs?limit=${limit}`
		);
		return response.data;
	},

	/**
	 * Gmail OAuth: Get authorization URL
	 */
	getGmailAuthUrl: async () => {
		const response = await apiClient.get(
			"/api/v1/email-config/gmail/auth-url"
		);
		return response.data;
	},

	/**
	 * Gmail OAuth: Handle callback
	 */
	gmailCallback: async (code: string, state: string) => {
		const response = await apiClient.post(
			"/api/v1/email-config/gmail/callback",
			{
				code,
				state,
			}
		);
		return response.data;
	},

	/**
	 * Gmail OAuth: Disconnect
	 */
	disconnectGmail: async () => {
		const response = await apiClient.post(
			"/api/v1/email-config/gmail/disconnect"
		);
		return response.data;
	},
};

/**
 * OCR API endpoints
 */
export const ocrApi = {
	/**
	 * Extract invoice data from a single file (PDF or image)
	 */
	extractInvoice: async (file: File, userId: string) => {
		const formData = new FormData();
		formData.append("file", file);
		formData.append("user_id", userId);

		const response = await apiClient.post("/extract", formData, {
			headers: {
				"Content-Type": "multipart/form-data",
			},
		});
		return response.data;
	},

	/**
	 * Extract invoice data from multi-page PDF (batch processing)
	 */
	extractBatch: async (file: File) => {
		const formData = new FormData();
		formData.append("file", file);

		const response = await apiClient.post("/extract-batch", formData, {
			headers: {
				"Content-Type": "multipart/form-data",
			},
		});
		return response.data;
	},
};

/**
 * Chat API endpoints
 */
export const chatApi = {
	/**
	 * Send a chat message and get AI response
	 */
	sendMessage: async (query: string, userId: string = "1") => {
		const response = await apiClient.post("/chat", {
			query,
			user_id: userId,
		});
		return response.data;
	},

	/**
	 * Get suggested questions
	 */
	getSuggestions: async () => {
		const response = await apiClient.get("/chat/suggestions");
		return response.data;
	},
};

/**
 * Check if user is authenticated
 */
export const isAuthenticated = (): boolean => {
	return tokenManager.getToken() !== null;
};
