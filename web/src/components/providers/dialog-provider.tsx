"use client";

import {
	createContext,
	useCallback,
	useContext,
	useEffect,
	useMemo,
	useRef,
	useState,
	type ReactNode,
} from "react";
import { usePathname } from "next/navigation";
import ConfirmDialog from "@/components/ui/confirm-dialog";

export interface ConfirmDialogOptions {
	title: string;
	description: ReactNode;
	confirmLabel?: string;
	cancelLabel?: string;
	destructive?: boolean;
}

interface PendingConfirmation extends ConfirmDialogOptions {
	id: number;
	resolve: (confirmed: boolean) => void;
}

type Confirm = (options: ConfirmDialogOptions) => Promise<boolean>;

const DialogContext = createContext<Confirm | null>(null);
let globalConfirm: Confirm | null = null;

export function requestConfirmDialog(
	options: ConfirmDialogOptions,
): Promise<boolean> {
	return globalConfirm?.(options) ?? Promise.resolve(false);
}

/**
 * App-wide replacement for the browser's blocking `window.confirm`.
 * Callers can keep a simple async flow while every confirmation shares the
 * same accessible, themed dialog.
 */
export function DialogProvider({ children }: { children: ReactNode }) {
	const pathname = usePathname();
	const nextId = useRef(0);
	const previousPathname = useRef(pathname);
	const [pending, setPending] = useState<PendingConfirmation | null>(null);
	const pendingRef = useRef<PendingConfirmation | null>(null);

	const confirm = useCallback<Confirm>(
		(options) =>
			new Promise<boolean>((resolve) => {
				pendingRef.current?.resolve(false);
				const request = { ...options, id: nextId.current++, resolve };
				pendingRef.current = request;
				setPending(request);
			}),
		[],
	);

	const settle = useCallback((id: number, confirmed: boolean) => {
		const current = pendingRef.current;
		if (!current || current.id !== id) return;
		pendingRef.current = null;
		current.resolve(confirmed);
		setPending(null);
	}, []);

	useEffect(() => {
		if (previousPathname.current === pathname) return;
		previousPathname.current = pathname;
		const pendingId = pendingRef.current?.id;
		if (pendingId === undefined) return;
		const timeoutId = window.setTimeout(() => {
			settle(pendingId, false);
		}, 0);
		return () => {
			window.clearTimeout(timeoutId);
		};
	}, [pathname, settle]);

	const value = useMemo(() => confirm, [confirm]);
	useEffect(() => {
		globalConfirm = confirm;
		return () => {
			if (globalConfirm === confirm) globalConfirm = null;
			const current = pendingRef.current;
			pendingRef.current = null;
			current?.resolve(false);
		};
	}, [confirm]);

	return (
		<DialogContext.Provider value={value}>
			{children}
			{pending && (
				<ConfirmDialog
					open
					onOpenChange={(open) => {
						if (!open) settle(pending.id, false);
					}}
					title={pending.title}
					description={pending.description}
					confirmLabel={pending.confirmLabel ?? "Continue"}
					cancelLabel={pending.cancelLabel}
					destructive={pending.destructive}
					onConfirm={() => {
						settle(pending.id, true);
					}}
				/>
			)}
		</DialogContext.Provider>
	);
}

export function useConfirmDialog(): Confirm {
	const context = useContext(DialogContext);
	if (!context) {
		throw new Error("useConfirmDialog must be used within DialogProvider");
	}
	return context;
}
