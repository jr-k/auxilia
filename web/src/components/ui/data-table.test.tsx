import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DataTable, type DataTableColumn } from "./data-table";

interface Row {
	id: string;
	name: string;
}

const columns: DataTableColumn<Row>[] = [
	{ key: "name", header: "Name", cell: (row) => row.name },
];
const rows: Row[] = Array.from({ length: 40 }, (_, index) => ({
	id: `row-${index}`,
	name: `Trigger ${index}`,
}));

function rowsContainer(name: string): HTMLElement {
	const container = screen.getByText(name).closest(".rounded-\\[10px\\]");
	if (!(container instanceof HTMLElement)) {
		throw new Error("Missing rows container");
	}
	return container;
}

describe("DataTable", () => {
	it("scrolls a long body in a positioned container", () => {
		render(
			<DataTable columns={columns} rows={rows} rowKey={(row) => row.id} scrollBody />,
		);

		expect(rowsContainer("Trigger 39")).toHaveClass(
			"relative",
			"min-h-0",
			"overflow-y-auto",
		);
	});

	it("keeps a non-scrolling body positioned", () => {
		render(<DataTable columns={columns} rows={rows} rowKey={(row) => row.id} />);

		const container = rowsContainer("Trigger 39");
		expect(container).toHaveClass("relative", "overflow-hidden");
		expect(container).not.toHaveClass("overflow-y-auto");
	});
});
