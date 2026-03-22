const BACKEND = import.meta.env.VITE_BACKEND_URL ?? 'http://localhost:8000';

export interface Category {
	id: string;
	name: string;
}

export interface Account {
	id: string;
	name: string;
}

export interface ReceiptItem {
	name: string;
	price: string;
	action: 'accept' | 'categorize' | 'personal';
	category_override?: string;
}

export interface Receipt {
	source: 'camera' | 'upload' | 'manual';
	store: string;
	description?: string;
	date: string;
	total: string;
	default_category: string;
	source_account_id: string;
	personal: boolean;
	items: ReceiptItem[];
}

function authHeaders(token: string) {
	return { Authorization: `Bearer ${token}` };
}

export async function validateToken(fireflyUrl: string, token: string): Promise<string> {
	const res = await fetch(`${BACKEND}/auth/validate`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ firefly_url: fireflyUrl, token })
	});
	if (!res.ok) throw new Error('Invalid token');
	return (await res.json()).user;
}

export async function getExpenseAccounts(fireflyUrl: string, token: string): Promise<Account[]> {
	const res = await fetch(`${BACKEND}/expense-accounts?firefly_url=${encodeURIComponent(fireflyUrl)}`, {
		headers: authHeaders(token)
	});
	if (!res.ok) throw new Error('Failed to fetch expense accounts');
	return res.json();
}

export async function createCategory(fireflyUrl: string, token: string, name: string): Promise<Category> {
	const res = await fetch(`${BACKEND}/categories?firefly_url=${encodeURIComponent(fireflyUrl)}`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json', ...authHeaders(token) },
		body: JSON.stringify({ name })
	});
	if (!res.ok) throw new Error('Failed to create category');
	return res.json();
}

export async function getCategories(fireflyUrl: string, token: string): Promise<Category[]> {
	const res = await fetch(`${BACKEND}/categories?firefly_url=${encodeURIComponent(fireflyUrl)}`, {
		headers: authHeaders(token)
	});
	if (!res.ok) throw new Error('Failed to fetch categories');
	return res.json();
}

export async function getAccounts(fireflyUrl: string, token: string): Promise<Account[]> {
	const res = await fetch(`${BACKEND}/accounts?firefly_url=${encodeURIComponent(fireflyUrl)}`, {
		headers: authHeaders(token)
	});
	if (!res.ok) throw new Error('Failed to fetch accounts');
	return res.json();
}

export interface Deposit {
	source: string;
	description?: string;
	date: string;
	amount: string;
	category: string;
	destination_account_id: string;
}

export async function getRevenueAccounts(fireflyUrl: string, token: string): Promise<Account[]> {
	const res = await fetch(`${BACKEND}/revenue-accounts?firefly_url=${encodeURIComponent(fireflyUrl)}`, {
		headers: authHeaders(token)
	});
	if (!res.ok) throw new Error('Failed to fetch revenue accounts');
	return res.json();
}

export async function submitDeposit(
	fireflyUrl: string,
	token: string,
	deposit: Deposit
): Promise<string> {
	const res = await fetch(`${BACKEND}/deposit?firefly_url=${encodeURIComponent(fireflyUrl)}`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json', ...authHeaders(token) },
		body: JSON.stringify(deposit)
	});
	if (!res.ok) throw new Error('Failed to submit deposit');
	return (await res.json()).firefly_transaction_id;
}

export interface OcrItem {
	name: string;
	price: number;
	category: string | null;
}

export interface OcrResult {
	store: string | null;
	date: string | null;
	total: number | null;
	items: OcrItem[];
}

export async function ocrReceipt(file: File, categories: string[]): Promise<OcrResult> {
	const form = new FormData();
	form.append('file', file);
	form.append('categories', JSON.stringify(categories));
	const res = await fetch(`${BACKEND}/ocr`, { method: 'POST', body: form });
	if (!res.ok) {
		const body = await res.json().catch(() => null);
		throw new Error(body?.detail ?? 'OCR failed');
	}
	return res.json();
}

export async function submitReceipt(
	fireflyUrl: string,
	token: string,
	receipt: Receipt
): Promise<string> {
	const res = await fetch(`${BACKEND}/receipt?firefly_url=${encodeURIComponent(fireflyUrl)}`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json', ...authHeaders(token) },
		body: JSON.stringify(receipt)
	});
	if (!res.ok) throw new Error('Failed to submit receipt');
	return (await res.json()).firefly_transaction_id;
}
