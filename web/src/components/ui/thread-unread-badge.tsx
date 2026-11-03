import { cn } from "@/lib/utils";

export function ThreadUnreadBadge({
	className,
}: {
	className?: string;
}) {
	return (
		<span
			className={cn(
				"inline-flex shrink-0 items-center rounded-full bg-petrol px-1.5 py-0.5 text-[9px] font-bold leading-none text-white shadow-[0_1px_2px_rgba(22,78,59,0.2)] dark:bg-panel-terminal dark:text-sidebar dark:shadow-[0_0_0_1px_rgba(159,214,203,0.2),0_1px_4px_rgba(0,0,0,0.35)]",
				className,
			)}
		>
			New
		</span>
	);
}
