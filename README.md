# Cash Trace

Receipt capture PWA that pushes transactions to [Firefly III](https://www.firefly-iii.org/). Enter receipts with optional item-level triage — split by category, tag items as personal or shared — and submit directly to your Firefly instance.

## Features

- **Quick receipts** — store, amount, category, done
- **Itemized exceptions** — carve out individual items with different categories or personal tags
- **Split transactions** — multiple categories/tags automatically become Firefly split transactions
- **Personal/shared tagging** — filter expenses in Firefly using tags
- **Mobile-first PWA** — installable, designed for on-the-go use

## Architecture

```
SvelteKit PWA → FastAPI backend → Firefly III
```

The backend is a thin stateless proxy — Firefly III is the sole source of truth. Auth uses Firefly Personal Access Tokens directly (no separate user system).

## Development

### Prerequisites

- Python 3.12+ with [uv](https://docs.astral.sh/uv/)
- Node.js 22+ (use [fnm](https://github.com/Schniz/fnm): `fnm use 22`)
- A running Firefly III instance with a Personal Access Token

### Backend

```bash
cd backend
uv run uvicorn app.main:app --reload
```

API docs available at http://localhost:8000/docs.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Opens at http://localhost:5173. Connect to your Firefly instance on the login screen.

## Deployment

Cash Trace is designed to run alongside an existing Firefly III Docker setup.

1. Copy and configure the environment file:
   ```bash
   cp .env.cashtrace.example .env.cashtrace
   # Set CASHTRACE_DOMAIN to your domain
   ```

2. Deploy with Docker Compose:
   ```bash
   docker compose -f docker-compose.cashtrace.yml --env-file .env.cashtrace up -d --build
   ```

This starts three containers:
- **cashtrace-backend** — FastAPI on the `firefly_iii` network (can reach Firefly at `http://app:8080`)
- **cashtrace-frontend** — SvelteKit served via adapter-node
- **cashtrace-caddy** — Reverse proxy with automatic HTTPS via Let's Encrypt

In the app login screen, use `http://app:8080` as the Firefly URL (Docker internal network).

## Currency

SEK only (hardcoded). Amounts use Swedish formatting (comma decimal separator) in the UI.

## License

Private project.
