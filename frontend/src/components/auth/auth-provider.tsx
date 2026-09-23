"use client";

import {
	createContext,
	useContext,
	useEffect,
	useMemo,
	useState,
	type ReactNode,
} from "react";
import type { Session, User } from "@supabase/supabase-js";

import { tokenManager } from "@/lib/api/client";
import { getSupabaseBrowserClient } from "@/lib/supabase/client";

type AuthContextValue = {
	loading: boolean;
	session: Session | null;
	user: User | null;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

function syncSessionToLocalState(session: Session | null) {
	if (!session) {
		tokenManager.removeToken();
		return;
	}

	tokenManager.setToken(session.access_token);
	tokenManager.setUser({
		id: session.user.id,
		email: session.user.email ?? "",
		name:
			session.user.user_metadata?.full_name ??
			session.user.user_metadata?.name ??
			session.user.email ??
			"User",
		picture:
			session.user.user_metadata?.avatar_url ??
			session.user.user_metadata?.picture ??
			"",
	});
}

export function AuthProvider({ children }: { children: ReactNode }) {
	const [loading, setLoading] = useState(true);
	const [session, setSession] = useState<Session | null>(null);
	const [user, setUser] = useState<User | null>(null);

	useEffect(() => {
		let isMounted = true;

		let supabase;
		try {
			supabase = getSupabaseBrowserClient();
		} catch (error) {
			console.warn("Supabase auth is not configured yet:", error);
			setLoading(false);
			return () => {
				isMounted = false;
			};
		}

		const bootstrap = async () => {
			const {
				data: { session: currentSession },
			} = await supabase.auth.getSession();

			if (!isMounted) {
				return;
			}

			setSession(currentSession);
			setUser(currentSession?.user ?? null);
			syncSessionToLocalState(currentSession);
			setLoading(false);
		};

		void bootstrap();

		const {
			data: { subscription },
		} = supabase.auth.onAuthStateChange((_event, nextSession) => {
			if (!isMounted) {
				return;
			}

			setSession(nextSession);
			setUser(nextSession?.user ?? null);
			syncSessionToLocalState(nextSession);
			setLoading(false);
		});

		return () => {
			isMounted = false;
			subscription.unsubscribe();
		};
	}, []);

	const value = useMemo(
		() => ({
			loading,
			session,
			user,
		}),
		[loading, session, user]
	);

	return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
	const context = useContext(AuthContext);
	if (!context) {
		throw new Error("useAuth must be used within AuthProvider");
	}

	return context;
}
