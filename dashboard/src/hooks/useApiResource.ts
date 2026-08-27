import { useCallback, useEffect, useState } from "react";
import type { ResourceStatus } from "../types/map";

export interface ApiResourceState<T> {
  data: T[] | null;
  status: ResourceStatus;
  error: string | null;
  retry: () => void;
}

interface Settled<T> {
  token: number;
  data: T[] | null;
  status: "success" | "empty" | "error";
  error: string | null;
}

// Each dataset (segments/routes/reports/alerts) is fetched independently
// through its own hook instance, so one failing endpoint never blocks or
// crashes the others. "loading" is derived by comparing `reloadToken`
// (bumped synchronously by retry()) against the token the last settled
// result belongs to — every setState call here runs inside the fetch's own
// then/catch callback, never synchronously in the effect body.
export function useApiResource<T>(fetcher: () => Promise<T[]>): ApiResourceState<T> {
  const [reloadToken, setReloadToken] = useState(0);
  const [settled, setSettled] = useState<Settled<T>>({ token: -1, data: null, status: "empty", error: null });

  useEffect(() => {
    let cancelled = false;

    fetcher()
      .then((result) => {
        if (cancelled) return;
        setSettled({ token: reloadToken, data: result, status: result.length === 0 ? "empty" : "success", error: null });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setSettled({
          token: reloadToken,
          data: null,
          status: "error",
          error: err instanceof Error ? err.message : "Request failed",
        });
      });

    return () => {
      cancelled = true;
    };
  }, [fetcher, reloadToken]);

  const retry = useCallback(() => setReloadToken((t) => t + 1), []);

  const isLoading = settled.token !== reloadToken;

  return {
    data: isLoading ? null : settled.data,
    status: isLoading ? "loading" : settled.status,
    error: isLoading ? null : settled.error,
    retry,
  };
}
