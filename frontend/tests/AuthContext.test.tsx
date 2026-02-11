import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { AuthProvider, useAuth } from "../src/contexts/AuthContext";

const { mockApi } = vi.hoisted(() => ({
  mockApi: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

vi.mock("../src/api/client", () => ({
  api: mockApi,
  AuthError: class extends Error {},
  ApiRequestError: class extends Error {
    constructor(
      public status: number,
      message: string,
    ) {
      super(message);
    }
  },
}));

function TestConsumer() {
  const { user, loading } = useAuth();
  if (loading) return <div>Loading</div>;
  return <div>{user ? `Logged in as ${user.email}` : "Not logged in"}</div>;
}

describe("AuthContext", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows loading state initially then resolves", async () => {
    mockApi.get.mockRejectedValueOnce(new Error("Not authenticated"));
    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    );

    expect(screen.getByText("Loading")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("Not logged in")).toBeInTheDocument();
    });
  });

  it("fetches current user on mount", async () => {
    mockApi.get.mockResolvedValueOnce({
      id: "1",
      email: "user@example.com",
      is_active: true,
      created_at: new Date().toISOString(),
    });

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText("Logged in as user@example.com")).toBeInTheDocument();
    });
    expect(mockApi.get).toHaveBeenCalledWith("/api/v1/auth/me");
  });

  it("throws when useAuth is used outside AuthProvider", () => {
    // Suppress console.error for this test
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(<TestConsumer />)).toThrow(
      "useAuth must be used within an AuthProvider",
    );
    spy.mockRestore();
  });
});
