// Client-side data fetching hooks for OpportunityOS.

"use client";

import { useState, useEffect, useCallback } from "react";

export interface UseApiState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

export function useApi<T>(
  fetcher: () => Promise<T>,
  deps: unknown[] = [],
): UseApiState<T> & { refetch: () => void } {
  const [state, setState] = useState<UseApiState<T>>({
    data: null,
    loading: true,
    error: null,
  });

  const load = useCallback(async () => {
    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      const data = await fetcher();
      setState({ data, loading: false, error: null });
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Unknown error";
      setState({ data: null, loading: false, error: message });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    load();
  }, [load]);

  return { ...state, refetch: load };
}
