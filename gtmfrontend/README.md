# GTM Frontend

Next.js 16 + Tailwind v4 leads dashboard for the GTM backend.

## Prerequisites

- Node.js 20+
- GTM backend running at `http://localhost:8002`

## Start the backend

```bash
cd ../gtmbackend
uv run python server.py
```

## Install & run

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Point to a different backend

```bash
NEXT_PUBLIC_API_URL=http://localhost:8002 npm run dev
```

Or set `NEXT_PUBLIC_API_URL` in a `.env.local` file.
