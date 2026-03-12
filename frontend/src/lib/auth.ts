import { writable } from 'svelte/store';
import { browser } from '$app/environment';

export interface AuthState {
	fireflyUrl: string;
	token: string;
}

function createAuthStore() {
	const stored = browser ? localStorage.getItem('auth') : null;
	const initial: AuthState | null = stored ? JSON.parse(stored) : null;

	const { subscribe, set } = writable<AuthState | null>(initial);

	return {
		subscribe,
		login(state: AuthState) {
			if (browser) localStorage.setItem('auth', JSON.stringify(state));
			set(state);
		},
		logout() {
			if (browser) localStorage.removeItem('auth');
			set(null);
		}
	};
}

export const auth = createAuthStore();
