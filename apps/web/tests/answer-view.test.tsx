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

  it("renders a lesson when no judge score is stored", () => {
    render(
      <AnswerView
        content={JSON.stringify({
          v: 1,
          lesson: [{ heading: "Answer", body: "Leaves capture sunlight." }],
          external: [],
          sources: [],
        })}
      />,
    );
    expect(screen.getByText("Leaves capture sunlight.")).toBeInTheDocument();
    expect(screen.queryByText(/faithfulness/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/relevance/i)).not.toBeInTheDocument();
  });

  it("does not render a numeric judge score", () => {
    render(
      <AnswerView
        content={JSON.stringify({
          v: 1,
          lesson: [{ heading: "Answer", body: "Leaves capture sunlight." }],
          external: [],
          sources: [],
          judge: {
            relevance: 0.17,
            faithfulness: 0.28,
            source_precision: 0.39,
            fabricated_timestamp: true,
          },
        })}
      />,
    );
    expect(screen.getByText("Leaves capture sunlight.")).toBeInTheDocument();
    expect(screen.queryByText("0.17")).not.toBeInTheDocument();
    expect(screen.queryByText("0.28")).not.toBeInTheDocument();
    expect(screen.queryByText("0.39")).not.toBeInTheDocument();
    expect(screen.queryByText(/faithfulness/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/source precision/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/fabricated/i)).not.toBeInTheDocument();
  });
});
