import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { SentimentCard } from "./SentimentCard";
import type { ArticleSentimentRead, SentimentMetadata, TeamSentimentRead } from "@/lib/api";

// ── Fixtures ──────────────────────────────────────────────────────────────────

const DISCLAIMER = "Scores reflect sentiment in sampled news headlines and summaries only.";
const FETCHED_AT = "2026-06-15T14:30:00.000Z";

function meta(overrides?: Partial<SentimentMetadata>): SentimentMetadata {
  return {
    analyzer: "vader-lexicon-v3.3",
    disclaimer: DISCLAIMER,
    sample_size: 20,
    ...overrides,
  };
}

function team(overrides?: Partial<TeamSentimentRead>): TeamSentimentRead {
  return {
    team_code: "BRA",
    team_name: "Brazil",
    article_count: 10,
    average_score: 0.34,
    label: "positive",
    confidence: 0.6,
    articles: [],
    ...overrides,
  };
}

function article(
  label: ArticleSentimentRead["label"],
  score: number,
  id: string,
): ArticleSentimentRead {
  return { article_id: id, title: `Article ${id}`, score, label, confidence: Math.abs(score) };
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("SentimentCard", () => {
  it("renders positive score with + prefix", () => {
    render(<SentimentCard team={team()} metadata={meta()} fetchedAt={FETCHED_AT} />);
    expect(screen.getByText("+0.34")).toBeInTheDocument();
  });

  it("renders positive label badge", () => {
    render(<SentimentCard team={team()} metadata={meta()} fetchedAt={FETCHED_AT} />);
    expect(screen.getByText("positive")).toBeInTheDocument();
  });

  it("renders negative score with − prefix", () => {
    render(
      <SentimentCard
        team={team({ average_score: -0.42, label: "negative" })}
        metadata={meta()}
        fetchedAt={FETCHED_AT}
      />,
    );
    expect(screen.getByText("-0.42")).toBeInTheDocument();
    expect(screen.getByText("negative")).toBeInTheDocument();
  });

  it("renders neutral score", () => {
    render(
      <SentimentCard
        team={team({ average_score: 0.01, label: "neutral", confidence: 0.01 })}
        metadata={meta()}
        fetchedAt={FETCHED_AT}
      />,
    );
    expect(screen.getByText("+0.01")).toBeInTheDocument();
    expect(screen.getByText("neutral")).toBeInTheDocument();
  });

  it("shows article count", () => {
    render(
      <SentimentCard
        team={team({ article_count: 7 })}
        metadata={meta()}
        fetchedAt={FETCHED_AT}
      />,
    );
    expect(screen.getByText(/7 articles/)).toBeInTheDocument();
  });

  it("uses singular 'article' when count is 1", () => {
    render(
      <SentimentCard
        team={team({ article_count: 1 })}
        metadata={meta()}
        fetchedAt={FETCHED_AT}
      />,
    );
    expect(screen.getByText("1 article")).toBeInTheDocument();
  });

  it("shows confidence as percentage", () => {
    render(
      <SentimentCard
        team={team({ confidence: 0.72 })}
        metadata={meta()}
        fetchedAt={FETCHED_AT}
      />,
    );
    expect(screen.getByText(/72%/)).toBeInTheDocument();
  });

  it("shows the limitations disclaimer", () => {
    render(<SentimentCard team={team()} metadata={meta()} fetchedAt={FETCHED_AT} />);
    expect(screen.getByText(DISCLAIMER)).toBeInTheDocument();
  });

  it("disclaimer element has role=note", () => {
    render(<SentimentCard team={team()} metadata={meta()} fetchedAt={FETCHED_AT} />);
    expect(screen.getByRole("note")).toBeInTheDocument();
  });

  it("methodology button is labelled 'Sentiment methodology'", () => {
    render(<SentimentCard team={team()} metadata={meta()} fetchedAt={FETCHED_AT} />);
    expect(screen.getByLabelText("Sentiment methodology")).toBeInTheDocument();
  });

  it("methodology disclosure contains VADER explanation", () => {
    render(<SentimentCard team={team()} metadata={meta()} fetchedAt={FETCHED_AT} />);
    expect(screen.getByText(/VADER/)).toBeInTheDocument();
  });

  it("shows analyzer name inside methodology tooltip", () => {
    render(<SentimentCard team={team()} metadata={meta()} fetchedAt={FETCHED_AT} />);
    expect(screen.getByText(/vader-lexicon-v3\.3/)).toBeInTheDocument();
  });

  it("gauge has accessible role=img with score in label", () => {
    render(
      <SentimentCard
        team={team({ average_score: 0.34, label: "positive" })}
        metadata={meta()}
        fetchedAt={FETCHED_AT}
      />,
    );
    expect(screen.getByRole("img", { name: /\+0\.34/ })).toBeInTheDocument();
  });

  it("hides article distribution when articles array is empty", () => {
    render(<SentimentCard team={team({ articles: [] })} metadata={meta()} fetchedAt={FETCHED_AT} />);
    expect(screen.queryByText("Article breakdown")).not.toBeInTheDocument();
  });

  it("shows article distribution when articles are provided", () => {
    const articles = [
      article("positive", 0.8, "1"),
      article("positive", 0.6, "2"),
      article("neutral", 0.0, "3"),
      article("negative", -0.5, "4"),
    ];
    render(
      <SentimentCard
        team={team({ articles })}
        metadata={meta()}
        fetchedAt={FETCHED_AT}
      />,
    );
    expect(screen.getByText("Article breakdown")).toBeInTheDocument();
    expect(screen.getByText("Positive")).toBeInTheDocument();
    expect(screen.getByText("Neutral")).toBeInTheDocument();
    expect(screen.getByText("Negative")).toBeInTheDocument();
  });

  it("distribution stacked bar has aria-label with counts", () => {
    const articles = [
      article("positive", 0.8, "1"),
      article("positive", 0.6, "2"),
      article("neutral", 0.0, "3"),
    ];
    render(
      <SentimentCard
        team={team({ articles })}
        metadata={meta()}
        fetchedAt={FETCHED_AT}
      />,
    );
    expect(
      screen.getByRole("img", { name: /2 positive, 1 neutral, 0 negative/ }),
    ).toBeInTheDocument();
  });

  it("renders zero-article team without crashing", () => {
    render(
      <SentimentCard
        team={team({ article_count: 0, average_score: 0.0, label: "neutral", confidence: 0.0 })}
        metadata={meta({ sample_size: 0 })}
        fetchedAt={FETCHED_AT}
      />,
    );
    expect(screen.getByText("+0.00")).toBeInTheDocument();
    expect(screen.getByText("0 articles")).toBeInTheDocument();
  });

  it("shows sample size in methodology panel", () => {
    render(
      <SentimentCard team={team()} metadata={meta({ sample_size: 47 })} fetchedAt={FETCHED_AT} />,
    );
    expect(screen.getByText(/47 articles in feed/)).toBeInTheDocument();
  });
});
