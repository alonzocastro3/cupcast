import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PredictionForm } from "./PredictionForm";
import type { PredictionSummary } from "@/lib/api";

// ── Mocks ────────────────────────────────────────────────────────────────────

vi.mock("@/lib/session", () => ({
  getSessionId: () => "test-session-id",
}));

const { mockSubmit } = vi.hoisted(() => ({ mockSubmit: vi.fn() }));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    api: {
      ...actual.api,
      matches: {
        ...actual.api.matches,
        submitPrediction: mockSubmit,
      },
    },
  };
});

// ── Helpers ──────────────────────────────────────────────────────────────────

const SUMMARY: PredictionSummary = {
  match_id: 1,
  total_predictions: 5,
  home_win_count: 3,
  draw_count: 1,
  away_win_count: 1,
  home_win_percentage: 60,
  draw_percentage: 20,
  away_win_percentage: 20,
};

function setup() {
  const onSuccess = vi.fn();
  const utils = render(<PredictionForm matchId={1} onSuccess={onSuccess} />);
  return { ...utils, onSuccess };
}

// ── Tests ────────────────────────────────────────────────────────────────────

describe("PredictionForm", () => {
  beforeEach(() => {
    mockSubmit.mockReset();
    localStorage.clear();
  });

  it("renders three outcome buttons", () => {
    setup();
    expect(screen.getByRole("button", { name: /home win/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /draw/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /away win/i })).toBeInTheDocument();
  });

  it("submit button is disabled when no outcome is selected", () => {
    setup();
    expect(screen.getByRole("button", { name: /submit prediction/i })).toBeDisabled();
  });

  it("enables submit after selecting an outcome", async () => {
    const user = userEvent.setup();
    setup();
    await user.click(screen.getByRole("button", { name: /home win/i }));
    expect(screen.getByRole("button", { name: /submit prediction/i })).not.toBeDisabled();
  });

  it("shows success state after successful submission", async () => {
    mockSubmit.mockResolvedValue({ prediction: { id: 1 }, summary: SUMMARY });
    const user = userEvent.setup();
    const { onSuccess } = setup();

    await user.click(screen.getByRole("button", { name: /home win/i }));
    await user.click(screen.getByRole("button", { name: /submit prediction/i }));

    await waitFor(() => {
      expect(screen.getByRole("status")).toHaveTextContent(/prediction submitted/i);
    });
    expect(onSuccess).toHaveBeenCalledWith(SUMMARY);
    expect(screen.getByRole("status")).toHaveTextContent(/home win/i);
  });

  it("shows duplicate message on 409 response", async () => {
    const { ApiError } = await import("@/lib/api");
    mockSubmit.mockRejectedValue(new ApiError(409, "/api/v1/matches/1/predictions"));
    const user = userEvent.setup();
    setup();

    await user.click(screen.getByRole("button", { name: /draw/i }));
    await user.click(screen.getByRole("button", { name: /submit prediction/i }));

    await waitFor(() => {
      expect(screen.getByRole("status")).toHaveTextContent(/already predicted/i);
    });
  });

  it("shows generic error on network failure", async () => {
    mockSubmit.mockRejectedValue(new Error("Network error"));
    const user = userEvent.setup();
    setup();

    await user.click(screen.getByRole("button", { name: /away win/i }));
    await user.click(screen.getByRole("button", { name: /submit prediction/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/something went wrong/i);
    });
  });

  it("shows validation error when only one score is entered", async () => {
    const user = userEvent.setup();
    setup();

    await user.click(screen.getByRole("button", { name: /home win/i }));
    await user.type(screen.getByLabelText(/home score/i), "2");
    await user.click(screen.getByRole("button", { name: /submit prediction/i }));

    expect(screen.getByRole("alert")).toHaveTextContent(/both scores or leave both empty/i);
    expect(mockSubmit).not.toHaveBeenCalled();
  });

  it("submits with scores when both are entered", async () => {
    mockSubmit.mockResolvedValue({ prediction: { id: 2 }, summary: SUMMARY });
    const user = userEvent.setup();
    setup();

    await user.click(screen.getByRole("button", { name: /home win/i }));
    await user.type(screen.getByLabelText(/home score/i), "2");
    await user.type(screen.getByLabelText(/away score/i), "1");
    await user.click(screen.getByRole("button", { name: /submit prediction/i }));

    await waitFor(() => expect(screen.getByRole("status")).toBeInTheDocument());
    expect(mockSubmit).toHaveBeenCalledWith(
      1,
      expect.objectContaining({
        predicted_home_score: 2,
        predicted_away_score: 1,
        predicted_outcome: "home_win",
        session_id: "test-session-id",
      }),
    );
  });

  it("shows duplicate state on mount when localStorage flag is set", () => {
    localStorage.setItem("cupcast_submitted_1", "1");
    setup();
    expect(screen.getByRole("status")).toHaveTextContent(/already predicted/i);
  });

  it("shows loading state during submission", async () => {
    let resolve: (v: unknown) => void;
    mockSubmit.mockReturnValue(new Promise((r) => { resolve = r; }));
    const user = userEvent.setup();
    setup();

    await user.click(screen.getByRole("button", { name: /home win/i }));
    await user.click(screen.getByRole("button", { name: /submit prediction/i }));

    expect(screen.getByRole("button", { name: /submitting/i })).toBeDisabled();
    resolve!({ prediction: { id: 3 }, summary: SUMMARY });
  });
});
