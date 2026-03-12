<script lang="ts">
	import { auth } from '$lib/auth';
	import { validateToken } from '$lib/api';
	import { goto } from '$app/navigation';

	let fireflyUrl = $state('http://localhost');
	let token = $state('');
	let error = $state('');
	let loading = $state(false);

	async function submit() {
		error = '';
		loading = true;
		try {
			await validateToken(fireflyUrl, token);
			auth.login({ fireflyUrl, token });
			goto('/');
		} catch {
			error = 'Could not connect. Check the URL and token.';
		} finally {
			loading = false;
		}
	}
</script>

<main>
	<div class="container">
		<h1>Cash Trace</h1>
		<p class="subtitle">Connect your Firefly III</p>

		<form class="card" onsubmit={(e) => { e.preventDefault(); submit(); }}>
			<div class="field">
				<label for="url">Firefly URL</label>
				<input id="url" type="url" bind:value={fireflyUrl} placeholder="http://localhost" required />
			</div>

			<div class="field">
				<label for="token">Personal Access Token</label>
				<input id="token" type="password" bind:value={token} placeholder="eyJ0eXAiOiJKV1Qi..." required />
			</div>

			{#if error}
				<p class="error">{error}</p>
			{/if}

			<button type="submit" class="btn btn-primary" disabled={loading}>
				{loading ? 'Connecting…' : 'Connect'}
			</button>
		</form>
	</div>
</main>

<style>
	main {
		display: flex;
		align-items: center;
		justify-content: center;
		min-height: 100dvh;
		padding: 1.5rem;
	}

	.container {
		width: 100%;
		max-width: 400px;
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	h1 {
		font-size: 1.75rem;
		font-weight: 700;
		text-align: center;
	}

	.subtitle {
		text-align: center;
		color: var(--color-muted);
		font-size: 0.95rem;
	}

	form {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}
</style>
