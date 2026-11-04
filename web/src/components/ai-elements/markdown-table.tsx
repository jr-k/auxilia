"use client";

import {
	type ComponentProps,
	type ReactNode,
	useContext,
	useEffect,
	useRef,
	useState,
} from "react";
import { createPortal } from "react-dom";
import { Download, Maximize2, X } from "lucide-react";
import {
	type ControlsConfig,
	type CSVSeparator,
	type ExtraProps,
	StreamdownContext,
	TableCopyDropdown,
	extractTableDataFromElement,
	tableDataToCSV,
	tableDataToMarkdown,
} from "streamdown";
import { cn } from "@/lib/utils";

type MarkdownTableProps = ComponentProps<"table"> & ExtraProps;
type TableControl = "copy" | "download" | "fullscreen";
type ExportFormat = "csv" | "markdown" | "json";

function tableControlEnabled(
	controls: ControlsConfig,
	control: TableControl,
): boolean {
	if (typeof controls === "boolean") return controls;
	const table = controls.table;
	if (table === false) return false;
	if (table === true || table == null) return true;
	return table[control] !== false;
}

function tableFilename(controls: ControlsConfig): string {
	if (typeof controls === "boolean" || typeof controls.table !== "object") {
		return "table";
	}
	const download = controls.table.download;
	return typeof download === "object" ? download.filename || "table" : "table";
}

function tableCsvSeparator(controls: ControlsConfig): CSVSeparator {
	if (typeof controls === "boolean" || typeof controls.table !== "object") {
		return ",";
	}
	return controls.table.csvSeparator ?? ",";
}

function tableMaxHeightStyle(
	maxHeight: number | string,
): { maxHeight: number | string } | undefined {
	if (maxHeight === 0 || maxHeight === Infinity) return undefined;
	return { maxHeight };
}

function tableDataToJson(table: HTMLTableElement): string {
	const data = extractTableDataFromElement(table);
	const counts = new Map<string, number>();
	const headers = data.headers.map((header, index) => {
		const base = header.trim() || `column_${index + 1}`;
		const count = (counts.get(base) ?? 0) + 1;
		counts.set(base, count);
		return count === 1 ? base : `${base}_${count}`;
	});
	const records = data.rows.map((row) =>
		Object.fromEntries(headers.map((header, index) => [header, row[index] ?? ""])),
	);
	return JSON.stringify(records, null, 2);
}

function downloadText(filename: string, content: string, type: string): void {
	const url = URL.createObjectURL(new Blob([content], { type }));
	const anchor = document.createElement("a");
	anchor.href = url;
	anchor.download = filename;
	anchor.click();
	URL.revokeObjectURL(url);
}

function TableExportDropdown({ className }: { className?: string }) {
	const [open, setOpen] = useState(false);
	const rootRef = useRef<HTMLDivElement>(null);
	const { controls, isAnimating } = useContext(StreamdownContext);

	useEffect(() => {
		const closeOutside = (event: MouseEvent) => {
			if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
		};
		document.addEventListener("mousedown", closeOutside);
		return () => {
			document.removeEventListener("mousedown", closeOutside);
		};
	}, []);

	const exportTable = (format: ExportFormat) => {
		const wrapper = rootRef.current?.closest(
			'[data-streamdown="table-wrapper"]',
		);
		const table = wrapper?.querySelector("table");
		if (!(table instanceof HTMLTableElement)) return;

		const data = extractTableDataFromElement(table);
		const base = tableFilename(controls);
		if (format === "csv") {
			downloadText(
				`${base}.csv`,
				tableDataToCSV(data, tableCsvSeparator(controls)),
				"text/csv",
			);
		} else if (format === "markdown") {
			downloadText(`${base}.md`, tableDataToMarkdown(data), "text/markdown");
		} else {
			downloadText(`${base}.json`, tableDataToJson(table), "application/json");
		}
		setOpen(false);
	};

	return (
		<div className="relative" ref={rootRef}>
			<button
				type="button"
				aria-label="Download table"
				title="Download table"
				disabled={isAnimating}
				onClick={() => {
					setOpen((value) => !value);
				}}
				className={cn(
					"cursor-pointer p-1 text-muted-foreground transition-all hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50",
					className,
				)}
			>
				<Download aria-hidden="true" size={14} />
			</button>
			{open && (
				<div className="absolute right-0 top-full z-20 mt-1 min-w-[120px] overflow-hidden rounded-md border border-border bg-background shadow-lg">
					{(
						[
							["csv", "CSV"],
							["markdown", "Markdown"],
							["json", "JSON"],
						] as const
					).map(([format, label]) => (
						<button
							key={format}
							type="button"
							title={`Download table as ${label}`}
							onClick={() => {
								exportTable(format);
							}}
							className="w-full px-3 py-2 text-left text-sm transition-colors hover:bg-muted/40"
						>
							{label}
						</button>
					))}
				</div>
			)}
		</div>
	);
}

function TableFullscreenButton({
	children,
	showCopy,
	showDownload,
}: {
	children: ReactNode;
	showCopy: boolean;
	showDownload: boolean;
}) {
	const [open, setOpen] = useState(false);
	const { isAnimating } = useContext(StreamdownContext);

	useEffect(() => {
		if (!open) return;
		const previousOverflow = document.body.style.overflow;
		document.body.style.overflow = "hidden";
		const closeOnEscape = (event: KeyboardEvent) => {
			if (event.key === "Escape") setOpen(false);
		};
		document.addEventListener("keydown", closeOnEscape);
		return () => {
			document.body.style.overflow = previousOverflow;
			document.removeEventListener("keydown", closeOnEscape);
		};
	}, [open]);

	return (
		<>
			<button
				type="button"
				aria-label="View fullscreen"
				title="View fullscreen"
				disabled={isAnimating}
				onClick={() => {
					setOpen(true);
				}}
				className="cursor-pointer p-1 text-muted-foreground transition-all hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
			>
				<Maximize2 aria-hidden="true" size={14} />
			</button>
			{open &&
				createPortal(
					<div
						role="dialog"
						aria-modal="true"
						aria-label="View fullscreen"
						data-streamdown="table-fullscreen"
						className="fixed inset-0 z-50 flex flex-col bg-background"
					>
						<div
							data-streamdown="table-wrapper"
							className="flex h-full flex-col"
						>
							<div className="flex items-center justify-end gap-1 p-4">
								{showCopy && <TableCopyDropdown />}
								{showDownload && <TableExportDropdown />}
								<button
									type="button"
									aria-label="Exit fullscreen"
									title="Exit fullscreen"
									onClick={() => {
										setOpen(false);
									}}
									className="rounded-md p-1 text-muted-foreground transition-all hover:bg-muted hover:text-foreground"
								>
									<X aria-hidden="true" size={20} />
								</button>
							</div>
							<div className="flex-1 overflow-auto p-4 pt-0 [&_thead]:sticky [&_thead]:top-0 [&_thead]:z-10">
								<table
									data-streamdown="table"
									className="w-full border-collapse border border-border"
								>
									{children}
								</table>
							</div>
						</div>
					</div>,
					document.body,
				)}
		</>
	);
}

export function MarkdownTable({
	children,
	className,
	...props
}: MarkdownTableProps) {
	delete props.node;
	const { controls, tableMaxHeight } = useContext(StreamdownContext);
	const showControls = typeof controls === "boolean" ? controls : true;
	const showCopy = tableControlEnabled(controls, "copy");
	const showDownload = tableControlEnabled(controls, "download");
	const showFullscreen = tableControlEnabled(controls, "fullscreen");

	return (
		<div
			data-streamdown="table-wrapper"
			className="my-4 flex flex-col gap-2 rounded-lg border border-border bg-sidebar p-2"
		>
			{showControls && (showCopy || showDownload || showFullscreen) && (
				<div className="flex items-center justify-end gap-1">
					{showCopy && <TableCopyDropdown />}
					{showDownload && <TableExportDropdown />}
					{showFullscreen && (
						<TableFullscreenButton
							showCopy={showCopy}
							showDownload={showDownload}
						>
							{children}
						</TableFullscreenButton>
					)}
				</div>
			)}
			<div
				className="border-collapse overflow-x-auto overflow-y-auto rounded-md border border-border bg-background"
				style={tableMaxHeightStyle(tableMaxHeight)}
			>
				<table
					{...props}
					data-streamdown="table"
					className={cn("w-full divide-y divide-border", className)}
				>
					{children}
				</table>
			</div>
		</div>
	);
}
