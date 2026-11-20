import { cn } from "@/lib/utils";

export function ThreadUnreadBadge({
	className,
}: {
	className?: string;
}) {
	return (
		<span
			className={cn(
				"inline-flex shrink-0 items-center rounded-full bg-petrol px-1.5 py-0.5 text-[9px] font-semibold leading-none text-white dark:bg-panel-terminal dark:text-sidebar",
				className,
			)}
		>
			New
		</span>
	);
}
