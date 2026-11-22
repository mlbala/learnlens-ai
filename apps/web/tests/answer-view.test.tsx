import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AnswerView } from "@/components/lesson/answer-view";

describe("AnswerView", () => {
  it("renders sections and titled sources instead of raw markdown", () => {
    const content = JSON.stringify({
      v: 1,
      lesson: [{ heading: "What it is", body: "An agent loop repeats a goal until it is done." }],
      external: [{ heading: "What it is", body: "Papers describe this as a closed loop." }],
      sources: [
        {
          title: "Closed-loop security agents",
          url: "https://doi.org/10.1109/example",
          kind: "paper",
        },
      ],
      review_status: "accepted",
      reasons: ["origin_mix", "invented_timestamp"],
    });
    render(<AnswerView content={content} />);
    expect(screen.getByText("From the lesson")).toBeInTheDocument();
    expect(screen.getByText("From papers and official docs")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Closed-loop security agents" })).toHaveAttribute(
      "href",
      "https://doi.org/10.1109/example",
    );
    expect(screen.getByText("doi.org")).toBeInTheDocument();
    expect(screen.queryByText(/###/)).not.toBeInTheDocument();
    expect(screen.queryByText(/origin_mix/)).not.toBeInTheDocument();
    expect(screen.queryByText(/invented_timestamp/)).not.toBeInTheDocument();
  });
});
