# Frontend — Agent Instructions (SCRI Oncology Copilot)

This is the React SPA for **Sarah Cannon Research Institute (SCRI) Oncology Copilot**. Read [../AGENTS.md](../AGENTS.md) first — universal building rules and clinical domain constraints live there. This file adds frontend-specific conventions.

---

## 1. Stack

- **Framework:** Plain React SPA (Vite + TypeScript, strict mode). **Not Next.js** — do not suggest Next.js, SSR, server components, or file-based routing.
- **Styling:** Tailwind CSS. No CSS modules, styled-components, Emotion, or `.module.css` files. Global theme tokens live in `src/index.css`.
- **UI Primitives:** shadcn/ui. Add components via `pnpm dlx shadcn@latest add <name>` — do not hand-roll what shadcn already provides.
- **Routing:** React Router.
- **Auth:** `@supabase/supabase-js` (institutional email only — no third-party Google/social OAuth).
- **Streaming Client:** Native fetch SSE with `ReadableStream` — hand-parsed Vercel AI data-stream frames in `src/lib/useChatStream.ts`. `@ai-sdk/react` was removed (D-7); `useChat` was never used.

---

## 2. Package Manager

- **`pnpm` only.** Do not use `npm install` or `yarn add`. The lockfile is `pnpm-lock.yaml`. If `package-lock.json` or `yarn.lock` appears, remove it immediately.
- **Minimum Release Age (7 Days):** Configured via `.npmrc` (`minimum-release-age=10080` minutes). pnpm will reject package versions published less than 7 days ago to defend against typosquatting or compromised releases.

---

## 3. Dependency Policy

See universal policy in [../AGENTS.md](../AGENTS.md). Frontend-specific rules:

- **HTTP Requests:** Use the native browser `fetch` API through a typed client in `src/lib/http.ts` and `src/lib/api.ts`. **No axios, ky, got, superagent, or redaxios.**
- **Dates & Numbers:** Use native `Date` and `Intl.DateTimeFormat`. No moment, dayjs, or date-fns unless explicitly needed.
- **Utilities:** Use native `Array`, `Object`, and `Map` methods. No lodash or ramda.
- **State Management:** Native `useState`, `useReducer`, and `useContext` first. Avoid external state libraries (Zustand, Redux, MobX).
- **Forms:** Native `<form>` + `FormData` first.

---

## 4. Directory Layout (to be populated during build)

```text
frontend/
├── src/
│   ├── components/        # UI components (chat, citation popovers, trial viewer)
│   │   └── ui/            # shadcn/ui primitives (button, popover, badge, dialog)
│   ├── lib/               # Framework-agnostic helpers (http, api, auth, supabase, env)
│   ├── pages/             # Route-level screens (Chat, History, Trial Library)
│   ├── App.tsx            # React Router setup
│   ├── main.tsx           # App entrypoint
│   └── index.css          # Tailwind directives + clinical theme tokens
├── index.html
├── vite.config.ts
├── tsconfig.json
├── package.json
├── .env.example
├── .npmrc
└── AGENTS.md
```

Keep imports consistent with the `@/*` alias (e.g. `@/lib/api`, `@/components/citations/CitationBadge`).

---

## 5. Code Style & Clinical UX

- **Strict TypeScript:** No `any` annotations unless unavoidable; prefer `unknown` and narrow with type guards.
- **Small, Composable Components:** A 20-to-40 line component focused on one clinical UI responsibility is preferred over large monolithic screens.
- **Verbatim Evidence Display:** When rendering citations (`[NCT ID, Section]`), always provide hover/click popovers showing the exact verbatim protocol quote and amendment vintage.
- **Tailwind Classes Inline:** Global color tokens live in `src/index.css`.

---

## 6. Configuration & Security

- All environment reads go through `src/lib/env.ts`, which validates required variables on app initialization. Never call `import.meta.env` directly in components.
- Client variables are prefixed with `VITE_`.
- Never expose Supabase `service_role` keys or database connection strings to the frontend.

---

## 7. Backend Integration

- Communicates with FastAPI over JSON and Server-Sent Events (SSE). Base URL originates from `VITE_API_BASE_URL`.
- Always use the typed API wrapper from `@/lib/api` — it automatically injects the Supabase bearer token and handles errors.
- Never pass authentication tokens manually through component props.

---

## 8. Testing & Verification

- No frontend test runners (no Jest, Vitest, Playwright, or Cypress).
- Verification is done via compile-time type checking (`pnpm tsc --noEmit`), linting (`pnpm lint`), and interactive browser verification.

---

## 9. Anti-Patterns (Rejected)

- Reading `import.meta.env` directly outside `lib/env.ts`.
- Introducing third-party HTTP clients like Axios.
- Adding client-side vector search or direct OpenAI API calls in the browser.
- Using `any` to bypass TypeScript errors.
- Adding multiple conflicting state libraries (Zustand + Jotai + Redux).
- Re-implementing UI primitives that shadcn/ui already provides.
- Proposing Next.js, SSR, or Node.js server runtimes for the frontend.
