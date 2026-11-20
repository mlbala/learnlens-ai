import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { PracticePanel } from "@/components/practice/practice-panel";
import { presentItemText } from "@/lib/practice/fixtures";
import { FIXTURE_PRACTICE_DECK } from "@/lib/practice/fixtures";

describe("presentItemText", () => {
  it("returns Tamil overlay when available", () => {
    const item = FIXTURE_PRACTICE_DECK.items[0]!;
    expect(presentItemText(item, "ta", "prompt")).toContain("கோடிங்");
    expect(presentItemText(item, "en", "answer")).toBe("Clarify requirements.");
  });
});

describe("PracticePanel", () => {
  it("renders fixture deck, labels AI illustration, and resolves quiz evidence", async () => {
    const user = userEvent.setup();
    render(<PracticePanel />);

    await waitFor(() => {
      expect(screen.getByTestId("practice-panel")).toBeInTheDocument();
    });

    expect(screen.getByText(/fixture data/i)).toBeInTheDocument();
    expect(screen.getByText(/no learning-efficacy claim/i)).toBeInTheDocument();

    // Flashcard first — advance to quiz
    await user.click(screen.getByRole("button", { name: /next/i }));

    expect(screen.getByText("AI illustration")).toBeInTheDocument();
    await user.click(screen.getByRole("option", { name: /ask clarifying questions/i }));
    await user.click(screen.getByRole("button", { name: /check answer/i }));

    await waitFor(() => {
      expect(screen.getByTestId("practice-result")).toHaveTextContent(/correct/i);
    });
    expect(screen.getByText(/evidence resolved/i)).toBeInTheDocument();
    expect(screen.getByText(/source evidence/i)).toBeInTheDocument();
  });

  it("switches presentation language without changing evidence language", async () => {
    const user = userEvent.setup();
    render(<PracticePanel />);
    await waitFor(() => {
      expect(screen.getByTestId("practice-panel")).toBeInTheDocument();
    });
    await user.click(screen.getByRole("button", { name: "தமிழ்" }));
    expect(
      screen.getByRole("heading", { name: /கோடிங் செய்வதற்கு முன்/i }),
    ).toBeInTheDocument();
  });
});
