import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const fetchModels = vi.fn();
const ask = vi.fn();

vi.mock("@/lib/api", () => ({
  fetchModels: () => fetchModels(),
  ask: (question: string, model: string) => ask(question, model),
}));

import { AskPanel } from "@/components/AskPanel";

describe("AskPanel", () => {
  beforeEach(() => {
    fetchModels.mockReset();
    ask.mockReset();
    fetchModels.mockResolvedValue(["gpt-4o", "github:gpt-4o-mini"]);
  });

  it("disables Ask until question entered", async () => {
    render(<AskPanel />);
    expect(screen.getByRole("button", { name: /ask/i })).toHaveProperty("disabled", true);
  });

  it("shows answer and telemetry after submit", async () => {
    ask.mockResolvedValue({
      data: {
        answer: "Outstanding school.",
        model: "gpt-4o",
        schools: [
          {
            school_name: "GEMS Modern Academy",
            location: "Nad Al Sheba",
            latest_rating: "Outstanding",
            min_fee: 30000,
            max_fee: 63792,
            curriculums: ["Indian"],
          },
        ],
      },
      telemetry: {
        gpt4o: {
          model: "gpt-4o",
          input_tokens: 12,
          output_tokens: 8,
          cost_usd: 0.0025,
        },
      },
    });
    render(<AskPanel />);
    await userEvent.type(screen.getByLabelText("Question"), "Rating for GEMS?");
    await userEvent.click(screen.getByRole("button", { name: /ask/i }));
    await waitFor(() =>
      expect(screen.getByText("Outstanding school.")).toBeTruthy(),
    );
    expect(screen.getByText(/\$0\.0025/)).toBeTruthy();
  });

  it("shows friendly error when ask fails", async () => {
    ask.mockRejectedValue(new Error("Model 'gpt-4o' unavailable: missing API key"));
    render(<AskPanel />);
    await userEvent.type(screen.getByLabelText("Question"), "hello");
    await userEvent.click(screen.getByRole("button", { name: /ask/i }));
    await waitFor(() =>
      expect(screen.getByText(/unavailable/i)).toBeTruthy(),
    );
  });
});
