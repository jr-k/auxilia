"use client";

import { useEffect } from "react";

type Edge = "left" | "right";

interface EdgeSwipeOptions {
	edge: Edge;
	enabled?: boolean;
	onSwipe: () => void;
}

const EDGE_ZONE_PX = 28;
const TRIGGER_DISTANCE_PX = 56;
const MAX_VERTICAL_DRIFT_PX = 48;

export function useEdgeSwipe({
	edge,
	enabled = true,
	onSwipe,
}: EdgeSwipeOptions) {
	useEffect(() => {
		if (!enabled) return;

		let gesture:
			| {
					identifier: number;
					startX: number;
					startY: number;
			  }
			| undefined;

		const reset = () => {
			gesture = undefined;
		};

		const handleTouchStart = (event: TouchEvent) => {
			if (event.touches.length !== 1) {
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

			const isHorizontal =
				directionalDistance > 10 &&
				directionalDistance > verticalDistance * 1.15;
			if (isHorizontal && event.cancelable) event.preventDefault();

			if (
				directionalDistance >= TRIGGER_DISTANCE_PX &&
				directionalDistance > verticalDistance * 1.25
			) {
				reset();
				onSwipe();
			}
		};

		document.addEventListener("touchstart", handleTouchStart, {
			passive: true,
		});
		document.addEventListener("touchmove", handleTouchMove, {
			passive: false,
		});
		document.addEventListener("touchend", reset, { passive: true });
		document.addEventListener("touchcancel", reset, { passive: true });

		return () => {
			document.removeEventListener("touchstart", handleTouchStart);
			document.removeEventListener("touchmove", handleTouchMove);
			document.removeEventListener("touchend", reset);
			document.removeEventListener("touchcancel", reset);
		};
	}, [edge, enabled, onSwipe]);
}
