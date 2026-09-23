import { useCallback, useEffect, useState } from "react";

// 10x/hour - an explicit requirement, matches the backend Strava sync cadence
// and every existing panel.
export const REFRESH_MS = 6 * 60 * 1000;

/**
 * Fetch on mount + every REFRESH_MS. A failed refresh sets `error` but never
 * clears previously loaded `data`, so a transient failure keeps showing the
 * last good render instead of blanking the panel.
 */
export function usePolling<T>(fetcher: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const reload = useCallback(() => {
    return fetcher()
      .then((d) => {
        setData(d);
        setError(null);
        setLoaded(true);
      })
      .catch((err: Error) => setError(err.message));
  }, deps);

  useEffect(() => {
    reload();
    const id = setInterval(reload, REFRESH_MS);
    return () => clearInterval(id);
  }, [reload]);

  return { data, error, loaded, reload, setData };
}
