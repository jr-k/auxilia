"use client";

import {
	useCallback,
	useEffect,
	useRef,
	useState,
	type CSSProperties,
} from "react";

type Edge = "left" | "right";

interface EdgeSwipeOptions {
	edge: Edge;
	enabled?: boolean;
	open: boolean;
	onOpenChange: (open: boolean) => void;
	drawerWidth?: number;
}

const EDGE_ZONE_PX = 28;
const MAX_VERTICAL_DRIFT_PX = 48;
const DIRECTION_LOCK_PX = 8;
const OPEN_PROGRESS_THRESHOLD = 0.34;
const OPEN_VELOCITY_THRESHOLD = 0.35;
const DEFAULT_DRAWER_WIDTH_PX = 18 * 16;
const SETTLE_MIN_MS = 120;
const SETTLE_MAX_MS = 240;
const SETTLE_EASING = "cubic-bezier(0.22, 1, 0.36, 1)";

interface Gesture {
	identifier: number;
	startX: number;
	startY: number;
	engaged: boolean;
	lastDistance: number;
	lastTime: number;
	velocity: number;
}

function overlayFor(content: HTMLDivElement | null): HTMLElement | null {
	const candidate = content?.previousElementSibling;
	return candidate instanceof HTMLElement &&
		candidate.dataset.slot === "sheet-overlay"
		? candidate
		: null;
}

export function useEdgeSwipe({
	edge,
	enabled = true,
	open,
	onOpenChange,
	drawerWidth = DEFAULT_DRAWER_WIDTH_PX,
}: EdgeSwipeOptions) {
	const contentRef = useRef<HTMLDivElement>(null);
	const openRef = useRef(open);
	const distanceRef = useRef(0);
	const settleTimerRef = useRef<number | null>(null);
	const [gestureControlled, setGestureControlled] = useState(false);
	const [gestureStartDistance, setGestureStartDistance] = useState(0);

	useEffect(() => {
		openRef.current = open;
	}, [open]);

	const transformFor = useCallback(
		(distance: number) => {
			const hiddenDistance = Math.max(0, drawerWidth - distance);
			const offset = edge === "left" ? -hiddenDistance : hiddenDistance;
			return `translate3d(${offset}px, 0, 0)`;
		},
		[drawerWidth, edge],
	);

	const applyDistance = useCallback(
		(distance: number) => {
			const boundedDistance = Math.min(drawerWidth, Math.max(0, distance));
			distanceRef.current = boundedDistance;
			const content = contentRef.current;
			if (!content) return;

			content.style.animation = "none";
			content.style.transition = "none";
			content.style.transform = transformFor(boundedDistance);
			content.style.willChange = "transform";

			const overlay = overlayFor(content);
			if (overlay) {
				overlay.style.animation = "none";
				overlay.style.transition = "none";
				overlay.style.opacity = String(boundedDistance / drawerWidth);
				overlay.style.willChange = "opacity";
			}
		},
		[drawerWidth, transformFor],
	);

	const clearGestureStyles = useCallback(() => {
		const content = contentRef.current;
		if (!content) return;
		content.style.animation = "";
		content.style.transition = "";
		content.style.transform = "";
		content.style.willChange = "";

		const overlay = overlayFor(content);
		if (overlay) {
			overlay.style.animation = "";
			overlay.style.transition = "";
			overlay.style.opacity = "";
			overlay.style.willChange = "";
		}
	}, []);

	const settle = useCallback(
		(targetOpen: boolean) => {
			if (settleTimerRef.current !== null) {
				window.clearTimeout(settleTimerRef.current);
			}

			const content = contentRef.current;
			const targetDistance = targetOpen ? drawerWidth : 0;
			const remaining = Math.abs(targetDistance - distanceRef.current);
			const duration = Math.round(
				Math.min(
					SETTLE_MAX_MS,
					Math.max(
						SETTLE_MIN_MS,
						(remaining / drawerWidth) * SETTLE_MAX_MS,
					),
				),
			);

			if (!content) {
				onOpenChange(targetOpen);
				setGestureControlled(false);
				return;
			}

			content.style.animation = "none";
			content.style.transition = `transform ${duration}ms ${SETTLE_EASING}`;
			content.style.transform = transformFor(targetDistance);
			const overlay = overlayFor(content);
			if (overlay) {
				overlay.style.animation = "none";
				overlay.style.transition = `opacity ${duration}ms ${SETTLE_EASING}`;
				overlay.style.opacity = targetOpen ? "1" : "0";
			}

			settleTimerRef.current = window.setTimeout(() => {
				settleTimerRef.current = null;
				distanceRef.current = targetDistance;
				if (targetOpen) {
					content.style.transition = "none";
					content.style.transform = transformFor(drawerWidth);
					content.style.willChange = "";
					if (overlay) {
						overlay.style.transition = "none";
						overlay.style.opacity = "1";
						overlay.style.willChange = "";
					}
					return;
				}

				onOpenChange(false);
				window.requestAnimationFrame(() => {
					setGestureControlled(false);
					clearGestureStyles();
				});
			}, duration);
		},
		[
			clearGestureStyles,
			drawerWidth,
			onOpenChange,
			transformFor,
		],
	);

	const handleSheetOpenChange = useCallback(
		(nextOpen: boolean) => {
			if (!nextOpen) {
				if (settleTimerRef.current !== null) {
					window.clearTimeout(settleTimerRef.current);
					settleTimerRef.current = null;
				}
				setGestureControlled(false);
				clearGestureStyles();
			}
			onOpenChange(nextOpen);
		},
		[clearGestureStyles, onOpenChange],
	);

	useEffect(() => {
		if (!enabled) return;

		let gesture: Gesture | undefined;

		const reset = () => {
			gesture = undefined;
		};

		const handleTouchStart = (event: TouchEvent) => {
			if (openRef.current || event.touches.length !== 1) {
				reset();
				return;
			}

			const touch = event.touches[0];
			const startsAtEdge =
				edge === "left"
					? touch.clientX <= EDGE_ZONE_PX
					: touch.clientX >= window.innerWidth - EDGE_ZONE_PX;
			if (!startsAtEdge) {
				reset();
				return;
			}

			gesture = {
				identifier: touch.identifier,
				startX: touch.clientX,
				startY: touch.clientY,
				engaged: false,
				lastDistance: 0,
				lastTime: event.timeStamp,
				velocity: 0,
			};
		};

		const handleTouchMove = (event: TouchEvent) => {
			if (!gesture) return;
			const touch = Array.from(event.touches).find(
				(candidate) => candidate.identifier === gesture?.identifier,
			);
			if (!touch) {
				reset();
				return;
			}

			const deltaX = touch.clientX - gesture.startX;
			const deltaY = touch.clientY - gesture.startY;
			const directionalDistance = edge === "left" ? deltaX : -deltaX;
			const verticalDistance = Math.abs(deltaY);

			if (
				directionalDistance < -12 ||
				(verticalDistance > MAX_VERTICAL_DRIFT_PX &&
					verticalDistance > Math.abs(deltaX))
			) {
				reset();
				return;
			}

			if (!gesture.engaged) {
				const isHorizontal =
					directionalDistance >= DIRECTION_LOCK_PX &&
					directionalDistance > verticalDistance * 1.15;
				if (!isHorizontal) return;

				gesture.engaged = true;
				distanceRef.current = Math.min(drawerWidth, directionalDistance);
				setGestureStartDistance(distanceRef.current);
				setGestureControlled(true);
				onOpenChange(true);
				window.requestAnimationFrame(() => {
					applyDistance(distanceRef.current);
				});
			}

			if (event.cancelable) event.preventDefault();
			const boundedDistance = Math.min(
				drawerWidth,
				Math.max(0, directionalDistance),
			);
			const elapsed = Math.max(1, event.timeStamp - gesture.lastTime);
			gesture.velocity =
				(boundedDistance - gesture.lastDistance) / elapsed;
			gesture.lastDistance = boundedDistance;
			gesture.lastTime = event.timeStamp;
			applyDistance(boundedDistance);
		};

		const handleTouchEnd = (event: TouchEvent) => {
			if (!gesture?.engaged) {
				reset();
				return;
			}
			const velocity =
				event.timeStamp - gesture.lastTime > 80 ? 0 : gesture.velocity;
			const shouldOpen =
				distanceRef.current / drawerWidth >= OPEN_PROGRESS_THRESHOLD ||
				velocity >= OPEN_VELOCITY_THRESHOLD;
			reset();
			settle(shouldOpen);
		};

		const handleTouchCancel = () => {
			const wasEngaged = gesture?.engaged === true;
			reset();
			if (wasEngaged) settle(false);
		};

		document.addEventListener("touchstart", handleTouchStart, {
			passive: true,
		});
		document.addEventListener("touchmove", handleTouchMove, {
			passive: false,
		});
		document.addEventListener("touchend", handleTouchEnd, { passive: true });
		document.addEventListener("touchcancel", handleTouchCancel, {
			passive: true,
		});

		return () => {
			document.removeEventListener("touchstart", handleTouchStart);
			document.removeEventListener("touchmove", handleTouchMove);
			document.removeEventListener("touchend", handleTouchEnd);
			document.removeEventListener("touchcancel", handleTouchCancel);
			if (settleTimerRef.current !== null) {
				window.clearTimeout(settleTimerRef.current);
				settleTimerRef.current = null;
			}
		};
	}, [
		applyDistance,
		drawerWidth,
		edge,
		enabled,
		onOpenChange,
		settle,
	]);

	const progress =
		drawerWidth > 0 ? gestureStartDistance / drawerWidth : 0;
	const contentStyle: CSSProperties | undefined = gestureControlled
		? {
				animation: "none",
				transform: transformFor(gestureStartDistance),
				transition: "none",
				willChange: "transform",
			}
		: undefined;
	const overlayStyle: CSSProperties | undefined = gestureControlled
		? {
				animation: "none",
				opacity: progress,
				transition: "none",
				willChange: "opacity",
			}
		: undefined;

	return {
		contentRef,
		contentStyle,
		gestureControlled,
		handleSheetOpenChange,
		overlayStyle,
	};
}
