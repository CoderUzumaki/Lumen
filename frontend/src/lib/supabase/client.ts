"use client";

import { createClient } from "@supabase/supabase-js";

let browserClient:
	| ReturnType<typeof createClient>
	| undefined;

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

export function getSupabaseBrowserClient() {
	if (!browserClient) {
		if (!supabaseUrl) {
			throw new Error(
				"NEXT_PUBLIC_SUPABASE_URL is not set. Add it to frontend/.env.local before using authentication."
			);
		}

		if (!supabaseAnonKey) {
			throw new Error(
				"NEXT_PUBLIC_SUPABASE_ANON_KEY is not set. Add it to frontend/.env.local before using authentication."
			);
		}

		browserClient = createClient(
			supabaseUrl,
			supabaseAnonKey
		);
	}

	return browserClient;
}
