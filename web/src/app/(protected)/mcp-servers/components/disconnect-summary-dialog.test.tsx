import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DisconnectSummaryDialog } from "./disconnect-summary-dialog";

describe("DisconnectSummaryDialog", () => {
	it("renders local successes, provider warnings, failures, and reconnect links", () => {
		render(
			<DisconnectSummaryDialog
				open
				onOpenChange={vi.fn()}
				summary={{
					disconnected: [
						{
							serverId: "server-1",
							serverName: "Docs",
							providerRevocation: "failed",
							warning:
								"The local connection was removed, but the provider could not be notified.",
						},
					],
					alreadyAbsent: [
						{ serverId: "server-2", serverName: "Already gone" },
					],
					failed: [
						{
							serverId: "server-3",
							serverName: "CRM",
							detail: "Auxilia could not remove the local connection.",
						},
					],
					unaffectedShared: [
						{ serverId: "server-4", serverName: "Shared search" },
					],
				}}
			/>,
		);

		expect(screen.getByText("Docs")).toBeInTheDocument();
		expect(
			screen.getByText(/provider could not be notified/i),
		).toBeInTheDocument();
		expect(screen.getByText("CRM")).toBeInTheDocument();
		expect(screen.getByText(/already absent/i)).toBeInTheDocument();
		expect(screen.getByText(/shared integration/i)).toBeInTheDocument();
		expect(screen.getByRole("link", { name: "Reconnect" })).toHaveAttribute(
			"href",
			"/mcp-servers/server-1",
		);
	});
});
