/**
 * Typed API client for the SCRI Oncology Copilot FastAPI backend.
 *
 * Responsibilities:
 * - Inject the Supabase session JWT as a Bearer token on every request.
 * - Throw a typed ApiError for non-2xx responses so callers never silently
 *   swallow backend error messages.
 * - Expose typed endpoint helpers (api.trials, api.chat) so components never
 *   construct raw URL strings or manage headers themselves.
 */

import { env } from "@/lib/env";
import { supabase } from "@/lib/supabase";

// ---------------------------------------------------------------------------
// Error type
// ---------------------------------------------------------------------------

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

// ---------------------------------------------------------------------------
// Core fetch wrapper
// ---------------------------------------------------------------------------

/**
 * Authenticated fetch against the FastAPI backend.
 *
 * Retrieves the active Supabase session JWT and attaches it as a Bearer token.
 * Throws ApiError for non-2xx responses so callers can handle them uniformly.
 */
async function apiFetch(
  path: string,
  options: RequestInit = {}
): Promise<Response> {
  const { data: sessionData } = await supabase.auth.getSession();
  const token = sessionData.session?.access_token;

  // A missing token means the coordinator is not signed in. Throw early rather
  // than sending an unauthenticated request that the backend will reject with 403.
  if (!token) {
    throw new ApiError(401, "No active session. Please sign in.");
  }

  const headers = new Headers(options.headers);
  headers.set("Authorization", `Bearer ${token}`);
  headers.set("Content-Type", "application/json");

  const response = await fetch(`${env.apiBaseUrl}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    // Attempt to parse FastAPI's standard { detail: string } error body.
    let detail = `HTTP ${response.status}`;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // Response body was not JSON — fall back to the status string.
    }
    throw new ApiError(response.status, detail);
  }

  return response;
}

// ---------------------------------------------------------------------------
// Typed endpoint surface
// ---------------------------------------------------------------------------

/** Metadata for a single landmark clinical trial.
 *
 * Field names match the real `clinical_trials` DB columns exactly (D-6).
 * Use these names when building the Phase 5.6 /api/trials response schema.
 */
export interface TrialSummary {
  nct_id: string;
  brief_title: string;
  /** Tumor program: 'Breast' | 'Lung' | 'Colorectal' | 'Melanoma' | 'Hematologic' */
  category: string;
  /** JSONB array e.g. ['PHASE2', 'PHASE3'] — display as phases.join('/') */
  phases: string[] | null;
  /** Overall recruitment status e.g. 'RECRUITING' */
  status: string;
  /** Lead sponsor organization name */
  organization: string | null;
  start_date: string | null;
  primary_completion_date: string | null;
}

/** Structured protocol chunk from the trial chunking pipeline. */
export interface TrialChunkOut {
  id: string;
  nct_id: string;
  section_type: string;
  section_title: string;
  chunk_index: number;
  chunk_text: string;
  token_count: number;
}

/** Full protocol detail returned by GET /api/trials/:nct_id */
export interface TrialDetail extends TrialSummary {
  official_title: string | null;
  /** Stored as JSONB in `arms` column */
  arms: Record<string, unknown>[] | null;
  primary_outcomes: Record<string, unknown>[] | null;
  last_update_posted_date: string | null;
  conditions: string[] | null;
  chunks: TrialChunkOut[];
}

/** Identity returned by GET /api/me — mirrors the backend AuthenticatedUser model. */
export interface AuthenticatedUser {
  id: string;
  email: string;
  role: string;
}

/** Summary representation of a clinical screening chat thread. */
export interface ThreadOut {
  id: string;
  title: string;
  created_at: string;
}

/** Grounded citation attached to an assistant message. */
export interface CitationOut {
  id: string;
  message_id: string;
  chunk_id: string | null;
  nct_id: string;
  section_header: string;
  verbatim_quote: string;
  citation_index: number;
  last_update_posted_date?: string | null;
  created_at: string | null;
}

/** Turn within a screening chat thread. */
export interface MessageOut {
  id: string;
  thread_id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  metadata_json?: {
    feedback?: {
      rating?: "helpful" | "unhelpful";
      comment?: string | null;
      updated_at?: string;
    };
    [key: string]: any;
  } | null;
  citations: CitationOut[];
}

export const api = {
  /** Fetch the backend-verified identity of the current user. Smoke-test endpoint. */
  me: async (): Promise<AuthenticatedUser> => {
    const res = await apiFetch("/api/me");
    return res.json();
  },

  trials: {
    /** List trials matching optional category / search filters. */
    list: async (params?: {
      category?: string;
      search?: string;
    }): Promise<TrialSummary[]> => {
      const query = new URLSearchParams();
      if (params?.category) query.set("category", params.category);
      if (params?.search) query.set("search", params.search);
      const qs = query.toString();
      const res = await apiFetch(`/api/trials${qs ? `?${qs}` : ""}`);
      return res.json();
    },

    /** Retrieve full trial metadata and ordered protocol chunks. */
    get: async (nctId: string): Promise<TrialDetail> => {
      const res = await apiFetch(`/api/trials/${encodeURIComponent(nctId)}`);
      return res.json();
    },
  },

  chat: {
    /**
     * Open a streaming SSE connection to the chat endpoint.
     *
     * Returns the raw Response so the caller can consume the ReadableStream directly.
     */
    stream: async (
      body: {
        thread_id: string | null;
        message: string;
      },
      signal?: AbortSignal
    ): Promise<Response> => {
      return apiFetch("/api/chat/stream", {
        method: "POST",
        body: JSON.stringify(body),
        signal,
      });
    },

    /** List all chat threads for the current user. */
    threads: async (): Promise<ThreadOut[]> => {
      const res = await apiFetch("/api/chat/threads");
      return res.json();
    },

    /** Create a new screening thread. */
    createThread: async (title?: string): Promise<ThreadOut> => {
      const res = await apiFetch("/api/chat/threads", {
        method: "POST",
        body: JSON.stringify(title ? { title } : {}),
      });
      return res.json();
    },

    /** Delete a screening thread by UUID. */
    deleteThread: async (threadId: string): Promise<void> => {
      await apiFetch(`/api/chat/threads/${threadId}`, {
        method: "DELETE",
      });
    },

    /** Fetch message history for a thread. */
    messages: async (threadId: string): Promise<MessageOut[]> => {
      const res = await apiFetch(`/api/chat/threads/${threadId}/messages`);
      return res.json();
    },

    /** Submit helpful / unhelpful clinical coordinator feedback on an assistant message. */
    feedback: async (
      messageId: string,
      rating: "helpful" | "unhelpful",
      comment?: string
    ): Promise<MessageOut> => {
      const res = await apiFetch(`/api/chat/messages/${messageId}/feedback`, {
        method: "POST",
        body: JSON.stringify({ rating, comment }),
      });
      return res.json();
    },
  },
};
