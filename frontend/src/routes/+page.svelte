<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/auth';
	import { getCategories, getAccounts, getExpenseAccounts, createCategory, submitReceipt, submitDeposit } from '$lib/api';
	import type { Category, Account, ReceiptItem } from '$lib/api';

	type Tab = 'out' | 'in';

	interface Item {
		id: number;
		name: string;
		price: string;
		category: string;
		personal: boolean;
	}

	let tab = $state<Tab>('out');

	let categories = $state<Category[]>([]);
	let accounts = $state<Account[]>([]);
	let expenseAccounts = $state<Account[]>([]);
	let loadError = $state('');

	// --- Out (receipt) state ---
	let newStore = $state(false);       // toggle: pick existing vs free-text
	let store = $state('');             // free-text (newStore=true) or existing account name
	let storeAccountId = $state('');    // existing expense account id (newStore=false)
	let description = $state('');
	let date = $state(new Date().toISOString().slice(0, 10));
	let total = $state('');
	let categoryId = $state('');
	let accountId = $state('');
	let receiptPersonal = $state(false);
	let nextId = 1;
	let items = $state<Item[]>([]);

	// --- Category creation ---
	let addingCategory = $state(false);
	let newCategoryName = $state('');
	let creatingCategory = $state(false);

	// --- In (deposit) state ---
	let depositSource = $state('');
	let depositDate = $state(new Date().toISOString().slice(0, 10));
	let depositAmount = $state('');
	let depositCategoryId = $state('');
	let depositAccountId = $state('');

	// --- Shared submission state ---
	let submitting = $state(false);
	let submitError = $state('');
	let successId = $state('');

	const itemsTotal = $derived(items.reduce((sum, i) => sum + (parseFloat(i.price) || 0), 0));
	const remainder = $derived((parseFloat(total) || 0) - itemsTotal);

	// The store name to send — either free text or the selected account's name
	const storeName = $derived(
		newStore ? store : (expenseAccounts.find(a => a.id === storeAccountId)?.name ?? '')
	);

	function clearStatus() { submitError = ''; successId = ''; }

	onMount(async () => {
		if (!$auth) return;
		try {
			[categories, accounts, expenseAccounts] = await Promise.all([
				getCategories($auth.fireflyUrl, $auth.token),
				getAccounts($auth.fireflyUrl, $auth.token),
				getExpenseAccounts($auth.fireflyUrl, $auth.token),
			]);
			if (categories.length) { categoryId = categories[0].id; depositCategoryId = categories[0].id; }
			if (accounts.length) { accountId = accounts[0].id; depositAccountId = accounts[0].id; }
			if (expenseAccounts.length) storeAccountId = expenseAccounts[0].id;
			else newStore = true; // no known stores yet, default to free text
		} catch {
			loadError = 'Failed to load data from Firefly.';
		}
	});

	async function addCategory() {
		if (!$auth || !newCategoryName.trim()) return;
		creatingCategory = true;
		try {
			const cat = await createCategory($auth.fireflyUrl, $auth.token, newCategoryName.trim());
			categories = [...categories, cat].sort((a, b) => a.name.localeCompare(b.name));
			categoryId = cat.id;
			newCategoryName = '';
			addingCategory = false;
		} catch {
			// keep the form open so user can retry
		} finally {
			creatingCategory = false;
		}
	}

	function addItem() {
		items = [...items, { id: nextId++, name: '', price: '', category: '', personal: false }];
	}

	function removeItem(id: number) {
		items = items.filter((i) => i.id !== id);
	}

	async function submitOut() {
		if (!$auth) return;
		submitting = true; clearStatus();
		const receiptItems: ReceiptItem[] = items
			.filter((i) => i.price)
			.map((i) => ({
				name: i.name || storeName,
				price: String(i.price),
				action: receiptPersonal || i.personal ? 'personal' : 'categorize',
				...(i.category ? { category_override: i.category } : {})
			}));
		try {
			const id = await submitReceipt($auth.fireflyUrl, $auth.token, {
				source: 'manual',
				store: storeName,
				description: description || undefined,
				date,
				total: String(total),
				default_category: categoryId,
				source_account_id: accountId,
				personal: receiptPersonal,
				items: receiptItems
			});
			successId = id;
			store = ''; description = ''; total = ''; items = []; receiptPersonal = false;
			if (expenseAccounts.length) newStore = false;
		} catch {
			submitError = 'Failed to submit. Try again.';
		} finally {
			submitting = false;
		}
	}

	async function submitIn() {
		if (!$auth) return;
		submitting = true; clearStatus();
		try {
			const id = await submitDeposit($auth.fireflyUrl, $auth.token, {
				source: depositSource,
				date: depositDate,
				amount: String(depositAmount),
				category: depositCategoryId,
				destination_account_id: depositAccountId,
			});
			successId = id;
			depositSource = ''; depositAmount = '';
		} catch {
			submitError = 'Failed to submit. Try again.';
		} finally {
			submitting = false;
		}
	}

	function fmt(n: number) {
		return n.toFixed(2).replace('.', ',') + ' kr';
	}
</script>

<main>
	<header>
		<span class="app-name">Cash Trace</span>
		<button class="logout" onclick={() => auth.logout()}>Sign out</button>
	</header>

	<div class="content">
		{#if loadError}
			<p class="error">{loadError}</p>
		{:else if !categories.length && !accounts.length}
			<p class="loading">Loading…</p>
		{:else if !categories.length}
			<p class="error">No categories found in Firefly. Add at least one category to get started.</p>
		{:else if !accounts.length}
			<p class="error">No asset accounts found in Firefly. Add at least one account to get started.</p>
		{:else}
			<div class="tabs">
				<button class="tab" class:active={tab === 'out'} onclick={() => { tab = 'out'; clearStatus(); }}>
					Out
				</button>
				<button class="tab" class:active={tab === 'in'} onclick={() => { tab = 'in'; clearStatus(); }}>
					In
				</button>
			</div>

			{#if tab === 'out'}
				<form onsubmit={(e) => { e.preventDefault(); submitOut(); }}>
					<div class="card header-card">

						<!-- Store field: dropdown or free text -->
						<div class="field">
							<div class="label-row">
								<label for="store">Store</label>
								<label class="new-toggle">
									<input type="checkbox" bind:checked={newStore} />
									New
								</label>
							</div>
							{#if newStore}
								<input id="store" type="text" bind:value={store} placeholder="Store name" required />
							{:else}
								<select id="store" bind:value={storeAccountId} required>
									{#each expenseAccounts as acc}
										<option value={acc.id}>{acc.name}</option>
									{/each}
								</select>
							{/if}
						</div>

						<!-- Description -->
						<div class="field">
							<label for="description">Description <span class="optional">(optional)</span></label>
							<input id="description" type="text" bind:value={description} placeholder="e.g. Birthday party food" />
						</div>

						<div class="row">
							<div class="field">
								<label for="date">Date</label>
								<input id="date" type="date" bind:value={date} required />
							</div>
							<div class="field">
								<label for="total">Amount (SEK)</label>
								<input id="total" type="text" inputmode="decimal" bind:value={total} placeholder="0.00" required />
							</div>
						</div>

						<!-- Category with inline add -->
						<div class="field">
							<div class="label-row">
								<label for="category">Category</label>
								<button type="button" class="add-cat-btn" onclick={() => { addingCategory = !addingCategory; newCategoryName = ''; }}>
									{addingCategory ? '✕' : '+ New'}
								</button>
							</div>
							{#if addingCategory}
								<div class="new-cat-row">
									<input
										type="text"
										bind:value={newCategoryName}
										placeholder="Category name"
										onkeydown={(e) => e.key === 'Enter' && (e.preventDefault(), addCategory())}
										autofocus
									/>
									<button type="button" class="btn-save-cat" onclick={addCategory} disabled={creatingCategory || !newCategoryName.trim()}>
										{creatingCategory ? '…' : 'Add'}
									</button>
								</div>
							{:else}
								<select id="category" bind:value={categoryId}>
									{#each categories as cat}
										<option value={cat.id}>{cat.name}</option>
									{/each}
								</select>
							{/if}
						</div>

						<div class="field">
							<label for="account">Account</label>
							<select id="account" bind:value={accountId}>
								{#each accounts as acc}
									<option value={acc.id}>{acc.name}</option>
								{/each}
							</select>
						</div>

						<label class="personal-check">
							<input type="checkbox" bind:checked={receiptPersonal} />
							Personal receipt
						</label>
					</div>

					{#if items.length > 0}
						<div class="items-list">
							{#each items as item (item.id)}
								<div class="card item-card">
									<div class="item-top">
										<input class="item-name" type="text" bind:value={item.name} placeholder="Item name" />
										<input class="item-price" type="text" inputmode="decimal" bind:value={item.price} placeholder="0.00" />
										<button type="button" class="remove-btn" onclick={() => removeItem(item.id)} aria-label="Remove">×</button>
									</div>
									<div class="item-bottom">
										<select bind:value={item.category} class="category-select">
											<option value="">{categories.find(c => c.id === categoryId)?.name ?? '—'}</option>
											{#each categories as cat}
												<option value={cat.id}>{cat.name}</option>
											{/each}
										</select>
										<label class="personal-check">
											<input type="checkbox" bind:checked={item.personal} />
											Personal
										</label>
									</div>
								</div>
							{/each}
						</div>
					{/if}

					<button type="button" class="add-btn" onclick={addItem}>+ Add item</button>

					{#if items.length > 0}
						<div class="card total-card">
							<div class="total-row">
								<span class="total-label">Remainder</span>
								<span class="total-amount" class:negative={remainder < 0}>{fmt(remainder)}</span>
							</div>
							<div class="total-row sub-row">
								<span class="total-label">Items</span>
								<span>{fmt(itemsTotal)}</span>
							</div>
						</div>
					{/if}

					{#if submitError}<p class="error">{submitError}</p>{/if}
					{#if successId}<p class="success">Saved to Firefly ✓</p>{/if}

					<button type="submit" class="btn btn-primary" disabled={submitting || remainder < 0}>
						{submitting ? 'Saving…' : 'Save to Firefly'}
					</button>
				</form>

			{:else}
				<form onsubmit={(e) => { e.preventDefault(); submitIn(); }}>
					<div class="card header-card">
						<div class="row">
							<div class="field">
								<label for="dep-source">Source</label>
								<input id="dep-source" type="text" bind:value={depositSource} placeholder="Employer" required />
							</div>
							<div class="field">
								<label for="dep-date">Date</label>
								<input id="dep-date" type="date" bind:value={depositDate} required />
							</div>
						</div>
						<div class="field">
							<label for="dep-amount">Amount (SEK)</label>
							<input id="dep-amount" type="text" inputmode="decimal" bind:value={depositAmount} placeholder="0.00" required />
						</div>
						<div class="row">
							<div class="field">
								<label for="dep-category">Category</label>
								<select id="dep-category" bind:value={depositCategoryId}>
									{#each categories as cat}
										<option value={cat.id}>{cat.name}</option>
									{/each}
								</select>
							</div>
							<div class="field">
								<label for="dep-account">Account</label>
								<select id="dep-account" bind:value={depositAccountId}>
									{#each accounts as acc}
										<option value={acc.id}>{acc.name}</option>
									{/each}
								</select>
							</div>
						</div>
					</div>

					{#if submitError}<p class="error">{submitError}</p>{/if}
					{#if successId}<p class="success">Saved to Firefly ✓</p>{/if}

					<button type="submit" class="btn btn-primary btn-income" disabled={submitting}>
						{submitting ? 'Saving…' : 'Save to Firefly'}
					</button>
				</form>
			{/if}
		{/if}
	</div>
</main>

<style>
	main {
		display: flex;
		flex-direction: column;
		min-height: 100dvh;
	}

	header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 1rem 1.25rem;
		background: var(--color-surface);
		box-shadow: var(--shadow);
		position: sticky;
		top: 0;
		z-index: 10;
	}

	.app-name { font-weight: 700; font-size: 1.1rem; }

	.logout {
		background: none;
		border: none;
		color: var(--color-muted);
		font-size: 0.875rem;
		cursor: pointer;
		padding: 0.25rem 0.5rem;
	}

	.content {
		flex: 1;
		padding: 1.25rem;
		max-width: 480px;
		width: 100%;
		margin: 0 auto;
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	/* Tabs */
	.tabs {
		display: grid;
		grid-template-columns: 1fr 1fr;
		background: var(--color-surface);
		border-radius: var(--radius);
		box-shadow: var(--shadow);
		overflow: hidden;
	}

	.tab {
		padding: 0.75rem;
		border: none;
		background: none;
		font-size: 0.95rem;
		font-weight: 600;
		color: var(--color-muted);
		cursor: pointer;
		transition: all 0.15s;
		border-bottom: 2px solid transparent;
	}

	.tab.active {
		color: var(--color-primary);
		border-bottom-color: var(--color-primary);
	}

	form {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	.header-card {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	.row {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0.75rem;
	}

	/* Label row with action on the right */
	.label-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}

	.new-toggle {
		display: flex;
		align-items: center;
		gap: 0.25rem;
		font-size: 0.8rem;
		color: var(--color-muted);
		font-weight: 400;
		text-transform: none;
		letter-spacing: 0;
		cursor: pointer;
	}

	.new-toggle input[type='checkbox'] {
		width: 0.875rem;
		height: 0.875rem;
		cursor: pointer;
	}

	.optional {
		font-weight: 400;
		text-transform: none;
		letter-spacing: 0;
		font-size: 0.75rem;
		color: var(--color-muted);
	}

	/* Category add */
	.add-cat-btn {
		background: none;
		border: none;
		color: var(--color-primary);
		font-size: 0.8rem;
		font-weight: 600;
		cursor: pointer;
		padding: 0;
	}

	.new-cat-row {
		display: grid;
		grid-template-columns: 1fr auto;
		gap: 0.5rem;
	}

	.btn-save-cat {
		padding: 0.75rem 1rem;
		background: var(--color-primary);
		color: #fff;
		border: none;
		border-radius: 0.5rem;
		font-weight: 600;
		cursor: pointer;
		white-space: nowrap;
	}

	.btn-save-cat:disabled { opacity: 0.5; cursor: not-allowed; }

	/* Items */
	.items-list {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.item-card {
		display: flex;
		flex-direction: column;
		gap: 0.625rem;
		padding: 0.875rem;
	}

	.item-top {
		display: grid;
		grid-template-columns: 1fr auto auto;
		gap: 0.5rem;
		align-items: center;
	}

	.item-name { min-width: 0; }
	.item-price { width: 6rem; }

	.remove-btn {
		background: none;
		border: none;
		color: var(--color-muted);
		font-size: 1.25rem;
		line-height: 1;
		cursor: pointer;
		padding: 0.25rem;
		border-radius: 0.25rem;
		transition: color 0.15s;
	}

	.remove-btn:hover { color: var(--color-danger); }

	.item-bottom {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}

	.category-select {
		flex: 1;
		padding: 0.5rem 0.75rem;
		border: 1.5px solid var(--color-border);
		border-radius: 0.5rem;
		font-size: 0.875rem;
		background: var(--color-surface);
		color: var(--color-text);
		-webkit-appearance: none;
		appearance: none;
	}

	.personal-check {
		display: flex;
		align-items: center;
		gap: 0.375rem;
		font-size: 0.875rem;
		color: var(--color-muted);
		cursor: pointer;
		white-space: nowrap;
		text-transform: none;
		letter-spacing: 0;
		font-weight: 400;
	}

	.personal-check input[type='checkbox'] {
		width: 1rem;
		height: 1rem;
		accent-color: #7c3aed;
		cursor: pointer;
	}

	.add-btn {
		width: 100%;
		padding: 0.75rem;
		border: 1.5px dashed var(--color-border);
		border-radius: var(--radius);
		background: none;
		color: var(--color-muted);
		font-size: 0.95rem;
		cursor: pointer;
		transition: all 0.15s;
	}

	.add-btn:hover {
		border-color: var(--color-primary);
		color: var(--color-primary);
	}

	/* Totals */
	.total-card {
		display: flex;
		flex-direction: column;
		gap: 0.375rem;
		padding: 0.875rem 1.25rem;
	}

	.total-row {
		display: flex;
		align-items: baseline;
		gap: 0.5rem;
	}

	.total-label {
		font-size: 0.875rem;
		color: var(--color-muted);
		text-transform: uppercase;
		letter-spacing: 0.05em;
		font-weight: 500;
	}

	.total-amount {
		font-size: 1.25rem;
		font-weight: 700;
		margin-left: auto;
	}

	.total-amount.negative { color: var(--color-danger); }

	.sub-row { opacity: 0.7; }
	.sub-row span:last-child { margin-left: auto; font-size: 0.95rem; }

	.loading {
		text-align: center;
		color: var(--color-muted);
		padding: 2rem;
	}

	.success {
		color: #16a34a;
		font-size: 0.875rem;
		font-weight: 500;
		text-align: center;
	}

	.btn-income { background: #16a34a; }
	.btn-income:hover { background: #15803d; }
</style>
