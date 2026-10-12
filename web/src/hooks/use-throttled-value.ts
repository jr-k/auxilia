import { useEffect, useRef, useState } from "react";

type ThrottleOptions<T> = {
	/** Changes when `value` may have been mutated without a new reference. */
	revision?: unknown;
	/** Snapshot taken only when the throttled value is emitted. */
	snapshot?: (value: T) => T;
};

const identity = <T>(value: T): T => value;

/**
 * Trailing throttle: re-emits `value` at most once per `intervalMs`. Bounds
 * how often the memoized conversation tree rebuilds under token streaming
 * (the stream store ticks once per SSE macrotask, i.e. per token).
 */
export function useThrottledValue<T>(
	value: T,
	intervalMs = 60,
	options?: ThrottleOptions<T>,
): T {
	const snapshot = options?.snapshot ?? identity;
	const revision = options?.revision ?? value;
	const [throttled, setThrottled] = useState(() => snapshot(value));
	const box = useRef({
		latest: value,
		snapshot,
		lastEmit: 0,
		timer: null as ReturnType<typeof setTimeout> | null,
	});

	useEffect(() => {
		const s = box.current;
		s.latest = value;
		s.snapshot = snapshot;
		if (s.timer != null) return;
		const wait = Math.max(0, intervalMs - (performance.now() - s.lastEmit));
		s.timer = setTimeout(() => {
			s.timer = null;
			s.lastEmit = performance.now();
			setThrottled(s.snapshot(s.latest));
		}, wait);
	}, [value, snapshot, revision, intervalMs]);

	useEffect(() => {
		const s = box.current;
		return () => {
			// Reset the handle too: StrictMode re-runs effects after this cleanup,
			// and a stale handle would make the emit effect above bail forever.
			if (s.timer != null) clearTimeout(s.timer);
			s.timer = null;
		};
	}, []);

	return throttled;
}
