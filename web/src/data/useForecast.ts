// Loads the files the page needs and keeps them in React state.
import { useCallback, useEffect, useState } from "react";
import { DataError, fetchConditions, fetchMeta, fetchRecommendations, fetchRiverFlow } from "./api";
import type { Conditions, Meta, Recommendations, RiverFlow } from "./generated/types";
import spotsJson from "./generated/spots.json";
import type { Spot } from "./derive";

export const SPOTS = spotsJson as Spot[];

export interface Forecast {
  status: "loading" | "ready" | "error";
  errorKind: "not-configured" | "other" | null;
  conditions: Record<string, Conditions | undefined>;
  recommendations: Recommendations | null;
  meta: Meta | null;
  reload: () => void;
}

export function useForecast(): Forecast {
  const [state, setState] = useState<Omit<Forecast, "reload">>({
    status: "loading", errorKind: null, conditions: {}, recommendations: null, meta: null,
  });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setState((s) => ({ ...s, status: "loading", errorKind: null }));
    Promise.allSettled([
      Promise.all(SPOTS.map((s) => fetchConditions(s.id))),
      fetchRecommendations(),
      fetchMeta(),
    ]).then(([cond, recs, meta]) => {
      if (cancelled) return;
      if (cond.status === "rejected") {
        const kind = cond.reason instanceof DataError && cond.reason.message === "not-configured" ? "not-configured" : "other";
        setState({ status: "error", errorKind: kind, conditions: {}, recommendations: null, meta: null });
        return;
      }
      setState({
        status: "ready", errorKind: null,
        conditions: Object.fromEntries(cond.value.map((c) => [c.spot_id, c])),
        recommendations: recs.status === "fulfilled" ? recs.value : null,
        meta: meta.status === "fulfilled" ? meta.value : null,
      });
    });
    return () => { cancelled = true; };
  }, [attempt]);

  const reload = useCallback(() => setAttempt((n) => n + 1), []);
  return { ...state, reload };
}

export interface RiverState { status: "idle" | "loading" | "ready" | "error"; data: RiverFlow | null; load: () => void }

/** River flow is only fetched when the visitor asks for it. */
export function useRiverFlow(): RiverState {
  const [state, setState] = useState<Omit<RiverState, "load">>({ status: "idle", data: null });
  const load = useCallback(() => {
    setState({ status: "loading", data: null });
    fetchRiverFlow().then(
      (data) => setState({ status: "ready", data }),
      () => setState({ status: "error", data: null }),
    );
  }, []);
  return { ...state, load };
}
