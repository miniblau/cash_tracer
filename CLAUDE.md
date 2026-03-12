# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Cash Trace

PWA + FastAPI backend that bridges receipt capture and Firefly III — handling item triage, personal/shared tagging, and transaction submission.

---

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   PWA UI    │────▶│   Backend   │────▶│  Firefly    │
│ (SvelteKit) │     │  (FastAPI)  │     │  (storage)  │
└─────────────┘     └─────────────┘     └─────────────┘
```

**Key principle**: Firefly III is source of truth. This tool is stateless — it processes and pushes, never stores.

## Tech Stack

| Component | Choice |
|-----------|--------|
| Frontend | SvelteKit 5 PWA (`@vite-pwa/sveltekit`, Svelte 5 runes) |
| Backend | FastAPI (Python 3.12+) |
| Storage | Firefly III (via Personal Access Token) |
| Proxy | Caddy (auto HTTPS) |
| Currency | SEK only |

## Data Models

```python
@dataclass
class ReceiptItem:
    name: str
    price: Decimal  # SEK
    action: Literal["accept", "categorize", "personal"]
    category_override: str | None = None  # Firefly category ID

@dataclass
class Receipt:
    source: Literal["camera", "upload", "manual"]
    store: str
    date: date
    total: Decimal              # Actual receipt total paid
    default_category: str       # Firefly category ID
    source_account_id: str      # Firefly asset account ID
    personal: bool = False      # If True, entire receipt tagged personal
    items: list[ReceiptItem]    # Exception items only

    @property
    def remainder(self) -> Decimal:
        """Total minus exception items → goes to default category."""
        return self.total - sum(i.price for i in self.items)
```

## Receipt Model

Receipts always have a total amount. Exception items are carved out from that total:
- **Remainder** (total - items) → default category, tagged "shared" (or "personal" if whole receipt is personal)
- **Exception items** → grouped by (category, personal) into separate splits
- All non-personal items tagged "shared", personal items tagged "personal"

This maps to Firefly split transactions when categories/tags differ.

## API Contracts

```
POST /auth/validate        { firefly_url, token } → { valid, user }
GET  /categories           → [{ id, name }]
GET  /accounts             → [{ id, name }]
POST /receipt              Receipt → { firefly_transaction_id }
```

Categories and accounts are fetched live from Firefly, never hardcoded.

## Commands

```bash
# Run backend (from backend/)
uv run uvicorn app.main:app --reload

# Run frontend (from frontend/) — requires Node 22+
npm run dev

# Add backend dependency
uv add <package>

# Deploy (from project root, alongside Firefly)
cp .env.cashtrace.example .env.cashtrace
# edit .env.cashtrace with your domain
docker compose -f docker-compose.cashtrace.yml --env-file .env.cashtrace up -d --build
```

Node 22+ required for frontend. Use fnm: `fnm use 22` (fnm installed at ~/.local/share/fnm).
API docs at http://localhost:8000/docs when backend is running.

## Deployment

Cash Trace runs alongside Firefly via `docker-compose.cashtrace.yml`. It joins the `firefly_iii` Docker network so the backend can reach Firefly at `http://app:8080`.

Caddy handles HTTPS automatically via Let's Encrypt. Set `CASHTRACE_DOMAIN` in `.env.cashtrace` to your domain before deploying. TLS certificates are persisted in the `caddy_data` volume.

In the app login, use `http://app:8080` as the Firefly URL (internal Docker network).

## File Naming

Use underscores: `receipt_item.py`, `firefly_client.py`

## Principles

- Walking skeleton: end-to-end first, then flesh out
- Small composable pieces
- Firefly is source of truth, tool stays thin

## Build Phases (current: Phase 3 done, Phase 5 partial)

- **Phase 0**: Firefly III running in Docker, test categories, PAT generated
- **Phase 1**: FastAPI scaffold + Firefly client (validate/categories/push transactions)
- **Phase 2**: PWA scaffold + auth + quick receipt end-to-end
- **Phase 3**: Itemized entry + split transactions + personal/shared tagging
- **Phase 4**: Claude Vision OCR integration + camera/upload UI *(not started)*
- **Phase 5**: Docker Compose deployment with Caddy *(done)*, PWA offline queue *(not started)*

## Security Notes

- `firefly_url` is passed per-request from the client. In production, consider restricting to known Firefly instances to prevent SSRF.
- Auth tokens are stored in localStorage — standard for PAT-based SPAs but be aware of XSS implications.
- Never commit `.env`, `.dev.env`, or `.db.env` files (see `.gitignore`).
