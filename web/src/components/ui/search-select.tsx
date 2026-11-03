"use client";

import * as DropdownMenuPrimitive from "@radix-ui/react-dropdown-menu";
import { Check, ChevronDown, Search } from "lucide-react";
import {
	useMemo,
	useRef,
	useState,
	type ReactNode,
} from "react";

import { cn } from "@/lib/utils";

export interface SearchSelectOption {
	value: string;
	label: string;
	description?: string;
	keywords?: string;
	icon?: ReactNode;
}

interface SearchSelectProps {
	value: string;
	options: SearchSelectOption[];
	onChange: (value: string) => void;
	ariaLabel: string;
	searchPlaceholder: string;
	active?: boolean;
	className?: string;
}

export function SearchSelect({
	value,
	options,
	onChange,
	ariaLabel,
	searchPlaceholder,
	active = false,
	className,
}: SearchSelectProps) {
	const inputRef = useRef<HTMLInputElement>(null);
	const [open, setOpen] = useState(false);
	const [query, setQuery] = useState("");
	const selected = options.find((option) => option.value === value) ?? options[0];
	const filteredOptions = useMemo(() => {
		const term = query.trim().toLowerCase();
		if (!term) return options;
		return options.filter((option) =>
			[
				option.label,
				option.description,
				option.keywords,
				option.value,
			]
				.filter(Boolean)
				.join(" ")
				.toLowerCase()
				.includes(term),
		);
	}, [options, query]);

	const handleOpenChange = (nextOpen: boolean) => {
		setOpen(nextOpen);
		if (nextOpen) {
			requestAnimationFrame(() => {
				inputRef.current?.focus();
			});
		} else {
			setQuery("");
		}
	};

	const choose = (nextValue: string) => {
		onChange(nextValue);
		setOpen(false);
	};

	return (
		<DropdownMenuPrimitive.Root
			open={open}
			onOpenChange={handleOpenChange}
			modal={false}
		>
			<DropdownMenuPrimitive.Trigger asChild>
				<button
					type="button"
					aria-label={ariaLabel}
					className={cn(
						"flex h-8 shrink-0 cursor-pointer items-center gap-2 rounded-[8px] border bg-card px-2.5 text-left outline-none transition-[border-color,box-shadow,background-color] hover:border-border-hover focus-visible:border-petrol/60 focus-visible:shadow-[0_0_0_3px_rgba(38,103,81,0.08)] dark:bg-card",
						active
							? "border-petrol/30 bg-petrol-tint/70 dark:border-panel-terminal/25 dark:bg-white/[0.06]"
							: "border-border dark:border-white/10",
						className,
					)}
				>
					{selected?.icon && (
						<span className="shrink-0 text-meta [&_svg]:size-3.5">
							{selected.icon}
						</span>
					)}
					<span className="max-w-36 truncate text-[11.5px] font-medium text-foreground">
						{selected?.label}
					</span>
					<ChevronDown
						className={cn(
							"size-3.5 shrink-0 text-meta transition-transform",
							open && "rotate-180",
						)}
					/>
				</button>
			</DropdownMenuPrimitive.Trigger>

			<DropdownMenuPrimitive.Portal>
				<DropdownMenuPrimitive.Content
					align="start"
					sideOffset={5}
					collisionPadding={16}
					className="z-[70] w-[min(280px,calc(100vw-2rem))] overflow-hidden rounded-[11px] border border-border bg-card shadow-[0_18px_50px_rgba(10,25,30,0.16)] data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:slide-in-from-top-1 dark:border-white/10"
				>
					<div className="border-b border-border p-2 dark:border-white/10">
						<div className="flex h-9 items-center gap-2 rounded-[7px] border border-input bg-background px-2.5 transition-colors focus-within:border-petrol/60">
							<Search className="size-3.5 shrink-0 text-meta" />
							<input
								ref={inputRef}
								type="search"
								value={query}
								aria-label={searchPlaceholder}
								placeholder={searchPlaceholder}
								onChange={(event) => {
									setQuery(event.target.value);
								}}
								onKeyDown={(event) => {
									if (event.key === "Enter" && filteredOptions[0]) {
										event.preventDefault();
										choose(filteredOptions[0].value);
										return;
									}
									if (event.key !== "Escape") event.stopPropagation();
								}}
								className="min-w-0 flex-1 bg-transparent text-[12px] text-foreground outline-none placeholder:text-meta"
							/>
						</div>
					</div>

					<div className="max-h-64 overflow-y-auto p-1.5 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
						{filteredOptions.map((option) => (
							<DropdownMenuPrimitive.Item
								key={option.value}
								onSelect={() => {
									choose(option.value);
								}}
								className={cn(
									"flex cursor-pointer select-none items-center gap-2.5 rounded-[7px] px-2.5 py-2 text-foreground outline-none transition-colors focus:bg-sidebar dark:focus:bg-white/5",
									option.value === value &&
										"bg-petrol-tint/70 dark:bg-white/[0.06]",
								)}
							>
								{option.icon && (
									<span className="shrink-0 text-meta [&_svg]:size-4">
										{option.icon}
									</span>
								)}
								<span className="min-w-0 flex-1">
									<span className="block truncate text-[12.5px] font-semibold">
										{option.label}
									</span>
									{option.description && (
										<span className="mt-0.5 block truncate text-[10.5px] text-meta">
											{option.description}
										</span>
									)}
								</span>
								{option.value === value && (
									<Check
										className="size-3.5 shrink-0 text-petrol dark:text-panel-terminal"
										strokeWidth={3}
									/>
								)}
							</DropdownMenuPrimitive.Item>
						))}
						{filteredOptions.length === 0 && (
							<div className="px-3 py-7 text-center">
								<Search className="mx-auto mb-2 size-4 text-meta" />
								<p className="text-[11.5px] font-medium text-meta">
									No matching filter
								</p>
							</div>
						)}
					</div>
				</DropdownMenuPrimitive.Content>
			</DropdownMenuPrimitive.Portal>
		</DropdownMenuPrimitive.Root>
	);
}
