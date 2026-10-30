import { cn } from "@/lib/utils";

export function TelegramLogo({ className }: { className?: string }) {
	return (
		<svg
			aria-hidden="true"
			viewBox="0 0 24 24"
			className={cn("shrink-0", className)}
		>
			<circle cx="12" cy="12" r="12" fill="#2AABEE" />
			<path
				fill="#fff"
				d="M18.7 6.2 16.8 18c-.14.84-.52 1.04-1.05.65l-2.9-2.14-1.4 1.35c-.16.15-.29.28-.59.28l.21-2.96 5.39-4.87c.23-.21-.05-.33-.36-.12l-6.66 4.19-2.87-.9c-.63-.2-.64-.63.13-.93l11.22-4.33c.52-.19.97.13.8.98Z"
			/>
		</svg>
	);
}
