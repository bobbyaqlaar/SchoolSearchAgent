import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/link", () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

import { SchoolCard } from "@/components/SchoolCard";

describe("SchoolCard", () => {
  it("links to slugified school detail page", () => {
    render(
      <SchoolCard
        result={{
          school_name: "GEMS Modern Academy",
          location: "Nad Al Sheba",
          latest_rating: "Outstanding",
          min_fee: 30000,
          max_fee: 63792,
          curriculums: ["Indian"],
        }}
      />,
    );
    const link = screen.getByRole("link", { name: /GEMS Modern Academy/i });
    expect(link.getAttribute("href")).toBe("/schools/gems-modern-academy");
    expect(screen.getByText("Outstanding")).toBeTruthy();
    expect(screen.getByText(/AED 30,000 – 63,792/)).toBeTruthy();
  });
});
