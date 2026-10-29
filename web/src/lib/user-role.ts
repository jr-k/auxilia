import type { WorkspaceRole } from "@/types/users";

const ROLE_LABELS: Record<WorkspaceRole, string> = {
	admin: "Admin",
	editor: "Editor",
	member: "Member",
};

export function userRoleLabel(user: {
	isInstanceOwner: boolean;
	role: WorkspaceRole;
}): string {
	return user.isInstanceOwner ? "Owner" : ROLE_LABELS[user.role];
}

export function workspaceRoleLabel(role: WorkspaceRole): string {
	return ROLE_LABELS[role];
}
