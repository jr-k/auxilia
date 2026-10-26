"use client";

import { memo, useEffect, useMemo, useRef, useState } from "react";
import type { BaseMessage } from "@langchain/core/messages";
import { isHumanMessage } from "@langchain/core/messages";

import {
	HoverCard,
	HoverCardContent,
	HoverCardTrigger,
} from "@/components/ui/hover-card";
import { presentSideChannelMessage } from "@/lib/transcript/side-channel-context";
import { cn } from "@/lib/utils";

type ThreadMapProps = {
	messages: BaseMessage[];
};

type PromptMarker = {
	anchorId: string;
	index: number;
	text: string;
};

export const threadMapAnchor = (messageIndex: number) =>
	`thread-prompt-${messageIndex}`;

function scrollContainerFor(element: HTMLElement): HTMLElement | null {
	let parent = element.parentElement;
	while (parent) {
		const overflowY = window.getComputedStyle(parent).overflowY;
		if (
			(overflowY === "auto" || overflowY === "scroll") &&
			parent.scrollHeight > parent.clientHeight
		) {
			return parent;
		}
		parent = parent.parentElement;
	}
	return null;
}

export const ThreadMap = memo(function ThreadMap({
	messages,
}: ThreadMapProps) {
	const [activeAnchorId, setActiveAnchorId] = useState<string | null>(null);
	const activeAnchorIdRef = useRef<string | null>(null);
	const markerListRef = useRef<HTMLDivElement | null>(null);
	const prompts = useMemo<PromptMarker[]>(
		() =>
			messages.flatMap((message, messageIndex) => {
				if (!isHumanMessage(message) || message.name === "host") return [];
				const displayText = message.additional_kwargs?.display_text;
				const source =
					typeof displayText === "string" ? displayText : message.text;
				const text = presentSideChannelMessage(source).text;
				return [
					{
						anchorId: threadMapAnchor(messageIndex),
						index: messageIndex,
						text: text.trim() || "Prompt with attachments",
					},
				];
			}),
		[messages],
	);
	const promptSignature = prompts.map((prompt) => prompt.anchorId).join("\0");

	useEffect(() => {
		if (prompts.length === 0) return;

		const anchors = prompts.flatMap((prompt) => {
			const element = document.getElementById(prompt.anchorId);
			return element ? [{ prompt, element }] : [];
		});
		if (anchors.length === 0) return;
		const activatePrompt = (active: PromptMarker) => {
			if (activeAnchorIdRef.current === active.anchorId) return;
			const markerList = markerListRef.current;
			if (activeAnchorIdRef.current) {
				const previous = markerList?.querySelector<HTMLElement>(
					`[data-prompt-anchor="${CSS.escape(activeAnchorIdRef.current)}"]`,
				);
				previous?.setAttribute("data-active", "false");
				previous?.removeAttribute("aria-current");
			}
			const next = markerList?.querySelector<HTMLElement>(
				`[data-prompt-anchor="${CSS.escape(active.anchorId)}"]`,
			);
			next?.setAttribute("data-active", "true");
			next?.setAttribute("aria-current", "location");
			activeAnchorIdRef.current = active.anchorId;
			setActiveAnchorId(active.anchorId);
			if (!markerList || !next) return;
			const markerTop = next.offsetTop;
			const markerBottom = markerTop + next.offsetHeight;
			const visibleTop = markerList.scrollTop;
			const visibleBottom = visibleTop + markerList.clientHeight;
			if (markerTop < visibleTop || markerBottom > visibleBottom) {
				markerList.scrollTop =
					markerTop - markerList.clientHeight / 2 + next.offsetHeight / 2;
			}
		};
		const scrollContainer = scrollContainerFor(anchors[0].element);
		if (!scrollContainer) {
			const frame = window.requestAnimationFrame(() => {
				activatePrompt(anchors[0].prompt);
			});
			return () => {
				window.cancelAnimationFrame(frame);
			};
		}

		let measureFrame: number | null = null;
		let positions: Array<{ prompt: PromptMarker; top: number }> = [];
		const updateActivePrompt = () => {
			if (positions.length === 0) return;
			const atTop = scrollContainer.scrollTop <= 2;
			const atBottom =
				scrollContainer.scrollTop + scrollContainer.clientHeight >=
				scrollContainer.scrollHeight - 2;
			let active = positions[0].prompt;
			if (atTop) {
				active = positions[0].prompt;
			} else if (atBottom) {
				active = positions.at(-1)?.prompt ?? active;
			} else {
				const activationOffset =
					scrollContainer.scrollTop +
					Math.min(180, scrollContainer.clientHeight * 0.3);
				let low = 0;
				let high = positions.length - 1;
				while (low <= high) {
					const middle = Math.floor((low + high) / 2);
					const candidate = positions[middle];
					if (candidate.top <= activationOffset) {
						active = candidate.prompt;
						low = middle + 1;
					} else {
						high = middle - 1;
					}
				}
			}
			activatePrompt(active);
		};
		const measurePositions = () => {
			measureFrame = null;
			const containerRect = scrollContainer.getBoundingClientRect();
			positions = anchors.map(({ prompt, element }) => ({
				prompt,
				top:
					element.getBoundingClientRect().top -
					containerRect.top +
					scrollContainer.scrollTop,
			}));
			updateActivePrompt();
		};
		const scheduleMeasure = () => {
			if (measureFrame !== null) return;
			measureFrame = window.requestAnimationFrame(measurePositions);
		};
		const handleScroll = () => {
			// Positions are measured only when layout changes. Scroll events can
			// then update the active marker synchronously with a binary search,
			// avoiding both layout reads and a one-frame React delay.
			updateActivePrompt();
		};

		scheduleMeasure();
		scrollContainer.addEventListener("scroll", handleScroll, {
			passive: true,
		});
		window.addEventListener("resize", scheduleMeasure);
		const resizeObserver = new ResizeObserver(scheduleMeasure);
		resizeObserver.observe(scrollContainer);
		const content = scrollContainer.firstElementChild;
		if (content instanceof HTMLElement) resizeObserver.observe(content);

		return () => {
			if (measureFrame !== null) {
				window.cancelAnimationFrame(measureFrame);
			}
			scrollContainer.removeEventListener("scroll", handleScroll);
			window.removeEventListener("resize", scheduleMeasure);
			resizeObserver.disconnect();
		};
	}, [promptSignature, prompts]);

	if (prompts.length < 2) return null;

	const jumpTo = (anchorId: string) => {
		const target = document.getElementById(anchorId);
		if (!target) return;
		const scrollContainer = scrollContainerFor(target);
		if (!scrollContainer) {
			target.scrollIntoView({
				behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
					? "auto"
					: "smooth",
				block: "center",
			});
			return;
		}
		const containerRect = scrollContainer.getBoundingClientRect();
		const targetTop =
			target.getBoundingClientRect().top -
			containerRect.top +
			scrollContainer.scrollTop;
		const activationOffset = Math.min(
			180,
			scrollContainer.clientHeight * 0.3,
		);
		scrollContainer.scrollTo({
			top: Math.max(0, targetTop - activationOffset + 1),
			behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
				? "auto"
				: "smooth",
		});
	};

	return (
		<nav
			aria-label="Conversation prompt map"
			className="pointer-events-none absolute right-3 top-1/2 z-20 hidden -translate-y-1/2 lg:block xl:right-5"
		>
			<div
				ref={markerListRef}
				className="pointer-events-auto max-h-[56vh] overflow-y-auto py-2 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
			>
				<div className="relative flex min-h-10 w-16 flex-col items-end py-1">
					<div
						aria-hidden="true"
						className="absolute bottom-0 right-5 top-0 w-px bg-gradient-to-b from-transparent via-border to-transparent"
					/>
					{prompts.map((prompt, promptIndex) => {
						const isActive =
							prompt.anchorId ===
							(activeAnchorId ?? prompts[0]?.anchorId);
						const rank = promptIndex + 1;
						const showRank = rank === 1 || rank % 5 === 0;
						const isMajor =
							promptIndex === 0 ||
							promptIndex === prompts.length - 1 ||
							rank % 5 === 0;

						return (
							<HoverCard
								key={`${prompt.anchorId}-${prompt.index}`}
								openDelay={100}
								closeDelay={60}
							>
								<HoverCardTrigger asChild>
									<button
										type="button"
										data-prompt-anchor={prompt.anchorId}
										data-active={isActive ? "true" : "false"}
										aria-current={isActive ? "location" : undefined}
										aria-label={`Go to prompt ${promptIndex + 1}: ${prompt.text}`}
										onClick={() => {
											jumpTo(prompt.anchorId);
										}}
										className="group relative z-10 flex h-[18px] w-16 cursor-pointer items-center justify-end pr-5 outline-none"
									>
										<span
											aria-hidden="true"
											className={cn(
												"block h-px origin-right rounded-full bg-meta/55 transition-[width,height,background-color] duration-75 ease-out group-data-[active=true]:h-0.5 group-data-[active=true]:w-8 group-data-[active=true]:bg-petrol group-data-[active=true]:shadow-[0_0_8px_rgba(20,64,70,0.35)]",
												isMajor ? "w-4" : "w-2.5",
												"group-hover:h-0.5 group-hover:w-7 group-hover:bg-petrol",
												"group-focus-visible:h-0.5 group-focus-visible:w-7 group-focus-visible:bg-petrol",
											)}
										/>
										{showRank && (
											<span
												aria-hidden="true"
												className={cn(
													"absolute right-0 w-4 text-right font-mono text-[9px] font-medium tabular-nums text-meta/65 transition-colors duration-75 group-data-[active=true]:font-semibold group-data-[active=true]:text-petrol",
													"group-hover:text-petrol group-focus-visible:text-petrol",
												)}
											>
												{rank}
											</span>
										)}
									</button>
								</HoverCardTrigger>
								<HoverCardContent
									side="left"
									align="center"
									sideOffset={12}
									className="pointer-events-none w-72 rounded-md border-hairline bg-card/95 p-3 shadow-raised backdrop-blur-md"
								>
									<p className="line-clamp-6 whitespace-pre-wrap text-[12.5px] font-medium leading-[1.55] text-foreground">
										{prompt.text}
									</p>
								</HoverCardContent>
							</HoverCard>
						);
					})}
				</div>
			</div>
		</nav>
	);
});
