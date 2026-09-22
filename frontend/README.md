# SCRI Oncology Copilot — Frontend SPA

The React 18+ Single Page Application (SPA) for the **Sarah Cannon Research Institute (SCRI) Oncology Copilot**. Built with Vite, TypeScript, Tailwind CSS, shadcn/ui, and Supabase Auth.

---

## 🚀 Quickstart

### 1. Prerequisites
- Node.js 20+ (LTS)
- [`pnpm`](https://pnpm.io/) package manager (mandatory per project standards)

### 2. Environment Setup
Copy the example environment file:

```bash
cp .env.example .env
```
*(On Windows PowerShell: `Copy-Item .env.example .env`)*

Ensure the following variables are populated in `frontend/.env`:
```dotenv
# Backend API base URL
VITE_API_BASE_URL=http://localhost:8000

# Supabase Auth credentials (browser-safe public keys only)
VITE_SUPABASE_URL=https://<your-project-ref>.supabase.co
VITE_SUPABASE_ANON_KEY=<your-anon-public-key>
```

> [!WARNING]
> Never place the `SUPABASE_SERVICE_ROLE_KEY` or direct database connection strings in `frontend/.env`. Only public, browser-safe keys belong here.

### 3. Install Dependencies
```bash
pnpm install
```

### 4. Run Development Server
```bash
pnpm dev
```

The application will start on [http://localhost:5173](http://localhost:5173).

---

## 🛠️ Available Scripts

| Command | Description |
| :--- | :--- |
| `pnpm dev` | Starts Vite local development server with hot module replacement (HMR) |
| `pnpm build` | Typechecks with `tsc -b` and builds production bundle in `dist/` |
| `pnpm preview` | Serves local production build for previewing |
| `pnpm lint` | Runs ESLint over project files |
| `pnpm tsc --noEmit` | Runs TypeScript type checker without building |

---

## 🛡️ Architecture & Rules

- **Single Source of Truth for Config:** All environment variables are validated and exported through [src/lib/env.ts](file:///d:/FarazAhmad-ai/projects/Sarah%20Cannon%20Research%20Institute%20%28SCRI%29/frontend/src/lib/env.ts). Never read `import.meta.env` directly in components.
- **Package Discipline:** Use `pnpm` exclusively (`minimum-release-age=10080`). Do not install `axios`, `lodash`, or `moment`.
- **UI & Styling:** Built with Tailwind CSS and shadcn/ui components for clean, accessible clinical UI primitives.

