import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
  AnswerView,
  WEB_NOTE_NOT_COVERED,
  WEB_NOTE_PARTLY_COVERED,
  WEB_NOTE_UNKNOWN,
} from "@/components/lesson/answer-view";

function webAnswer(extra: Record<string, unknown>) {
  return JSON.stringify({
    v: 1,
    lesson: [{ heading: "Coverage", body: "The video does not cover this question." }],
    external: [
      {
        heading: "Why RNNs struggle",
        body: "Recurrent networks process tokens one at a time, which limits parallel training.",
      },
    ],
    sources: [{ title: "RNN survey", url: "https://arxiv.org/abs/1506.00019", kind: "paper" }],
    decision: "blend",
    ...extra,
  });
}

describe("Web results coverage note", () => {
  it("says the question is not covered in the video and still shows the web answer last", () => {
    render(<AnswerView content={webAnswer({ video_covered: false })} />);
    expect(screen.getByTestId("web-coverage-note")).toHaveTextContent(WEB_NOTE_NOT_COVERED);
    expect(screen.getByText(/process tokens one at a time/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "RNN survey" })).toBeInTheDocument();
    const lesson = screen.getByText("From the lesson");
    const web = screen.getByText("From web search · not from the video");
    expect(lesson.compareDocumentPosition(web) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("says the video covers part of it when the video lane is covered", () => {
    render(<AnswerView content={webAnswer({ video_covered: true })} />);
    expect(screen.getByTestId("web-coverage-note")).toHaveTextContent(WEB_NOTE_PARTLY_COVERED);
  });

  it("falls back to a plain not-from-the-video note on older answers", () => {
    render(<AnswerView content={webAnswer({})} />);
    expect(screen.getByTestId("web-coverage-note")).toHaveTextContent(WEB_NOTE_UNKNOWN);
  });

  it("shows no web note when there is no web panel", () => {
    render(
      <AnswerView
        content={JSON.stringify({
          v: 1,
          lesson: [{ heading: "Answer", body: "Leaves capture sunlight." }],
          external: [],
          sources: [],
          video_covered: true,
        })}
      />,
    );
    expect(screen.queryByTestId("web-coverage-note")).not.toBeInTheDocument();
  });
});

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
    expect(screen.getByText("From web search · not from the video")).toBeInTheDocument();
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
