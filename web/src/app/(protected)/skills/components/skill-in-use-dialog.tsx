"use client";

import ResourceInUseDialog from "@/components/resource-in-use-dialog";
import type { BoundAgent } from "@/types/agents";

interface SkillInUseDialogProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	skillName: string | null;
	agents: BoundAgent[];
	onConfirm: () => Promise<void>;
}

export default function SkillInUseDialog({
	open,
	onOpenChange,
	skillName,
	agents,
	onConfirm,
}: SkillInUseDialogProps) {
	return (
		<ResourceInUseDialog
			open={open}
			onOpenChange={onOpenChange}
			resourceLabel="Skill"
			resourceName={skillName}
			agents={agents}
			consequence="access to this procedure"
			onConfirm={onConfirm}
		/>
	);
}
