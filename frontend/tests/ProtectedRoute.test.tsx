import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ProtectedRoute } from "../src/components/ProtectedRoute";
import { AuthProvider } from "../src/contexts/AuthContext";
import { BrowserRouter, Routes, Route } from "react-router-dom";

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

function renderWithRouter(initialPath = "/") {
  window.history.pushState({}, "", initialPath);
  return render(
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<div>Login Page</div>} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <div>Protected Content</div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </AuthProvider>
    </BrowserRouter>,
  );
}

describe("ProtectedRoute", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows loading state while auth is resolving", () => {
    mockApi.get.mockImplementation(() => new Promise(() => {}));
    renderWithRouter();
    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });

  it("redirects to /login when user is not authenticated", async () => {
    mockApi.get.mockRejectedValueOnce(new Error("Not authenticated"));
    renderWithRouter();

    await waitFor(() => {
      expect(screen.getByText("Login Page")).toBeInTheDocument();
    });
  });

  it("renders children when user is authenticated", async () => {
    mockApi.get.mockResolvedValueOnce({
      id: "1",
      email: "user@example.com",
      is_active: true,
      created_at: new Date().toISOString(),
    });

    renderWithRouter();

    await waitFor(() => {
      expect(screen.getByText("Protected Content")).toBeInTheDocument();
    });
  });
});
