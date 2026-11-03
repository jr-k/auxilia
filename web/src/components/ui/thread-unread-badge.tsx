import { cn } from "@/lib/utils";

export function ThreadUnreadBadge({
	className,
}: {
	className?: string;
}) {
	return (
		<span
			className={cn(
				"inline-flex shrink-0 items-center rounded-full bg-petrol px-1.5 py-0.5 text-[9px] font-bold leading-none text-white shadow-[0_1px_2px_rgba(22,78,59,0.2)] dark:bg-panel-terminal dark:text-panel-deep",
				className,
			)}
		>
			New
		</span>
	);
}
