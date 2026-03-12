<script lang="ts">
	import { auth } from '$lib/auth';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';

	let { children } = $props();

	$effect(() => {
		if ($auth === null && $page.url.pathname !== '/login') {
			goto('/login');
		}
	});
</script>

<svelte:head>
	<meta name="theme-color" content="#2563eb" />
</svelte:head>

{@render children()}

<style>
	:global(*) {
		box-sizing: border-box;
		margin: 0;
		padding: 0;
	}

	:global(:root) {
		--color-bg: #f5f5f5;
		--color-surface: #ffffff;
		--color-primary: #2563eb;
		--color-primary-dark: #1d4ed8;
		--color-danger: #dc2626;
		--color-text: #111827;
		--color-muted: #6b7280;
		--color-border: #e5e7eb;
		--radius: 0.75rem;
		--shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
	}

	:global(body) {
		font-family: system-ui, -apple-system, sans-serif;
		background: var(--color-bg);
		color: var(--color-text);
		min-height: 100dvh;
	}

	:global(input, select, button) {
		font-family: inherit;
		font-size: 1rem;
	}

	:global(.card) {
		background: var(--color-surface);
		border-radius: var(--radius);
		box-shadow: var(--shadow);
		padding: 1.5rem;
	}

	:global(.field) {
		display: flex;
		flex-direction: column;
		gap: 0.375rem;
	}

	:global(label) {
		font-size: 0.875rem;
		font-weight: 500;
		color: var(--color-muted);
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	:global(input[type='text']),
	:global(input[type='number']),
	:global(input[type='date']),
	:global(input[type='url']),
	:global(input[type='password']),
	:global(select) {
		width: 100%;
		padding: 0.75rem 1rem;
		border: 1.5px solid var(--color-border);
		border-radius: 0.5rem;
		background: var(--color-surface);
		color: var(--color-text);
		transition: border-color 0.15s;
		-webkit-appearance: none;
		appearance: none;
	}

	:global(input:focus),
	:global(select:focus) {
		outline: none;
		border-color: var(--color-primary);
	}

	:global(.btn) {
		display: block;
		width: 100%;
		padding: 0.875rem;
		border: none;
		border-radius: 0.5rem;
		font-size: 1rem;
		font-weight: 600;
		cursor: pointer;
		transition: background 0.15s;
	}

	:global(.btn-primary) {
		background: var(--color-primary);
		color: #fff;
	}

	:global(.btn-primary:hover) {
		background: var(--color-primary-dark);
	}

	:global(.btn-primary:disabled) {
		opacity: 0.6;
		cursor: not-allowed;
	}

	:global(.error) {
		color: var(--color-danger);
		font-size: 0.875rem;
	}
</style>
