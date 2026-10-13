"use client";

import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/lib/utils";

interface SelectableLeadingProps {
	children: React.ReactNode;
	selected: boolean;
	selectionMode: boolean;
	onToggle: (shiftKey: boolean) => void;
	label: string;
	disabled?: boolean;
	className?: string;
	hoverOnSelf?: boolean;
}

export function SelectableLeading({
	children,
	selected,
	selectionMode,
	onToggle,
	label,
	disabled = false,
	className,
	hoverOnSelf = false,
}: SelectableLeadingProps) {
	if (disabled) {
		return <span className={cn("shrink-0", className)}>{children}</span>;
	}

	return (
		<span
			className={cn(
				"relative grid shrink-0 place-items-center",
				hoverOnSelf && "group/selectable-leading",
				className,
			)}
		>
			<span
				aria-hidden={selectionMode || undefined}
				className={cn(
					"col-start-1 row-start-1 transition-[opacity,transform] duration-150",
					selectionMode
						? "scale-90 opacity-0"
						: hoverOnSelf
							? "opacity-100 group-hover/selectable-leading:scale-90 group-hover/selectable-leading:opacity-0"
							: "opacity-100 group-hover:scale-90 group-hover:opacity-0",
				)}
			>
				{children}
			</span>
			<span
				className={cn(
					"col-start-1 row-start-1 transition-[opacity,transform] duration-150",
					selectionMode
						? "pointer-events-auto scale-100 opacity-100"
						: hoverOnSelf
							? "pointer-events-none scale-90 opacity-0 group-hover/selectable-leading:pointer-events-auto group-hover/selectable-leading:scale-100 group-hover/selectable-leading:opacity-100 focus-within:pointer-events-auto focus-within:scale-100 focus-within:opacity-100"
							: "pointer-events-none scale-90 opacity-0 group-hover:pointer-events-auto group-hover:scale-100 group-hover:opacity-100 focus-within:pointer-events-auto focus-within:scale-100 focus-within:opacity-100",
				)}
			>
				<Checkbox
					checked={selected}
					aria-label={label}
					onCheckedChange={(_checked, event) => {
						onToggle(event.shiftKey);
					}}
				/>
			</span>
		</span>
	);
}
