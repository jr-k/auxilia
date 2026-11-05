"use client";

import * as DropdownMenuPrimitive from "@radix-ui/react-dropdown-menu";
import { Check, ChevronDown } from "lucide-react";
import { useState } from "react";

import { cn } from "@/lib/utils";
import type { MCPServerUrlOption } from "@/types/mcp-servers";

interface MCPServerUrlFieldProps {
	id: string;
	value: string;
	options: MCPServerUrlOption[];
	onChange: (value: string) => void;
	placeholder: string;
	inputClassName: string;
	invalid?: boolean;
}

export function MCPServerUrlField({
	id,
	value,
	options,
	onChange,
	placeholder,
	inputClassName,
	invalid = false,
}: MCPServerUrlFieldProps) {
	const [forceCustom, setForceCustom] = useState(false);
	const selectedOption = options.find((option) => option.url === value);
	const custom = options.length === 0 || forceCustom || !selectedOption;

	if (options.length === 0) {
		return (
			<input
				id={id}
				placeholder={placeholder}
				value={value}
				onChange={(event) => {
					onChange(event.target.value);
				}}
				aria-required="true"
				aria-invalid={invalid}
				className={inputClassName}
			/>
		);
	}

	return (
		<div className="flex flex-col gap-2">
			<DropdownMenuPrimitive.Root>
				<DropdownMenuPrimitive.Trigger asChild>
					<button
						id={custom ? `${id}-selector` : id}
						type="button"
						aria-label="Choose MCP server endpoint"
						className={cn(
							"group flex min-h-12 w-full cursor-pointer items-center gap-3 rounded-[10px] border bg-card px-3.5 py-2.5 text-left outline-none transition-[border-color,box-shadow,background-color] hover:border-border-hover focus-visible:border-petrol focus-visible:shadow-[0_0_0_3px_rgba(22,96,110,0.10)] dark:bg-card",
							invalid ? "border-destructive" : "border-input",
						)}
					>
						<span className="min-w-0 flex-1">
							<span className="block text-[12.5px] font-semibold text-foreground">
								{custom ? "Custom URL" : selectedOption?.label}
							</span>
							<span className="mt-0.5 block truncate font-mono text-[10.5px] text-meta dark:text-panel-dim">
								{custom ? value || "Enter another endpoint" : selectedOption?.url}
							</span>
						</span>
						<ChevronDown className="size-4 shrink-0 text-meta transition-transform group-data-[state=open]:rotate-180" />
					</button>
				</DropdownMenuPrimitive.Trigger>

				<DropdownMenuPrimitive.Portal>
					<DropdownMenuPrimitive.Content
						align="start"
						sideOffset={6}
						collisionPadding={16}
						className="z-[70] flex w-[min(420px,calc(100vw-2rem))] flex-col gap-px overflow-hidden rounded-[12px] border border-border bg-card p-1.5 shadow-[0_20px_55px_rgba(10,25,30,0.18)] data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:slide-in-from-top-1 dark:border-white/10"
					>
						{options.map((option) => {
							const selected = !custom && option.url === value;
							return (
								<DropdownMenuPrimitive.Item
									key={option.url}
									onSelect={() => {
										setForceCustom(false);
										onChange(option.url);
									}}
									className={cn(
										"flex cursor-pointer select-none items-start gap-3 rounded-[8px] px-3 py-2.5 text-foreground outline-none transition-colors focus:bg-sidebar dark:focus:bg-white/5",
										selected && "bg-petrol-tint/70 dark:bg-white/[0.06]",
									)}
								>
									<span className="min-w-0 flex-1">
										<span className="block text-[12.5px] font-semibold">
											{option.label}
										</span>
										<span className="mt-0.5 block truncate font-mono text-[10.5px] text-meta">
											{option.url}
										</span>
									</span>
									{selected && (
										<Check
											className="mt-1 size-3.5 shrink-0 text-petrol dark:text-panel-terminal"
											strokeWidth={3}
										/>
									)}
								</DropdownMenuPrimitive.Item>
							);
						})}
						<div className="my-1 h-px bg-border dark:bg-white/10" />
						<DropdownMenuPrimitive.Item
							onSelect={() => {
								setForceCustom(true);
							}}
							className={cn(
								"flex cursor-pointer select-none items-center gap-3 rounded-[8px] px-3 py-2.5 text-foreground outline-none transition-colors focus:bg-sidebar dark:focus:bg-white/5",
								custom && "bg-petrol-tint/70 dark:bg-white/[0.06]",
							)}
						>
							<span className="min-w-0 flex-1">
								<span className="block text-[12.5px] font-semibold">
									Custom URL
								</span>
								<span className="mt-0.5 block text-[10.5px] text-meta">
									Enter another Streamable HTTP endpoint
								</span>
							</span>
							{custom && (
								<Check
									className="size-3.5 shrink-0 text-petrol dark:text-panel-terminal"
									strokeWidth={3}
								/>
							)}
						</DropdownMenuPrimitive.Item>
					</DropdownMenuPrimitive.Content>
				</DropdownMenuPrimitive.Portal>
			</DropdownMenuPrimitive.Root>

			{custom && (
				<input
					id={id}
					autoFocus
					placeholder={placeholder}
					value={value}
					onChange={(event) => {
						onChange(event.target.value);
					}}
					aria-required="true"
					aria-invalid={invalid}
					className={inputClassName}
				/>
			)}
		</div>
	);
}
