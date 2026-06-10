import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ErrorState } from "@/components/ErrorState";

describe("ErrorState", () => {
  it("renders the message inside an alert", () => {
    render(<ErrorState message="Something went wrong" />);
    const alert = screen.getByRole("alert");
    expect(alert.textContent).toBe("Something went wrong");
  });
});
