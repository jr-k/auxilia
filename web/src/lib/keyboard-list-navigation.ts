import type { KeyboardEvent } from "react";

const OPTION_SELECTOR =
	'[data-keyboard-option="true"]:not([disabled]):not([aria-disabled="true"])';

function isTextEntry(element: EventTarget | null): boolean {
	return (
		element instanceof HTMLInputElement ||
		element instanceof HTMLTextAreaElement
	);
}

/**
 * Adds list-style arrow and Enter navigation while leaving Tab to the
 * browser's native focus order. Escape remains owned by the surrounding
 * dialog or menu primitive.
 */
export function handleKeyboardListNavigation(
	event: KeyboardEvent<HTMLElement>,
): void {
	if (event.defaultPrevented) return;
	if (event.altKey || event.ctrlKey || event.metaKey) return;
	if (
		event.key !== "ArrowDown" &&
		event.key !== "ArrowUp" &&
		event.key !== "Enter"
	) {
		return;
	}

	const options = Array.from(
		event.currentTarget.querySelectorAll<HTMLElement>(OPTION_SELECTOR),
	).filter((option) => option.offsetParent !== null);
	if (options.length === 0) return;

	const focusedIndex = options.findIndex(
		(option) => option === document.activeElement,
	);

	if (event.key === "Enter") {
		if (!isTextEntry(event.target)) return;
		event.preventDefault();
		options[0]?.click();
		return;
	}

	event.preventDefault();
	const direction = event.key === "ArrowDown" ? 1 : -1;
	const nextIndex =
		focusedIndex < 0
			? direction > 0
				? 0
				: options.length - 1
			: (focusedIndex + direction + options.length) % options.length;
	options[nextIndex]?.focus();
}
