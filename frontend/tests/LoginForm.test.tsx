import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { LoginForm } from "../src/components/LoginForm";
import { AuthProvider } from "../src/contexts/AuthContext";
import { BrowserRouter } from "react-router-dom";

// Mock the api client
vi.mock("../src/api/client", () => ({
  api: {
    get: vi.fn().mockRejectedValue(new Error("Not authenticated")),
    post: vi.fn(),
  },
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

async function renderWithProviders(ui: React.ReactElement) {
  const result = render(
    <BrowserRouter>
      <AuthProvider>{ui}</AuthProvider>
    </BrowserRouter>,
  );
  // Wait for AuthProvider's initial fetchUser() to settle
  await waitFor(() => {
    expect(screen.getByRole("button", { name: /login/i })).toBeInTheDocument();
  });
  return result;
}

describe("LoginForm", () => {
  it("renders email and password inputs", async () => {
    await renderWithProviders(<LoginForm />);
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
  });

  it("renders a submit button", async () => {
    await renderWithProviders(<LoginForm />);
    expect(screen.getByRole("button", { name: /login/i })).toBeInTheDocument();
  });

  it("requires email and password fields", async () => {
    await renderWithProviders(<LoginForm />);
    const emailInput = screen.getByLabelText(/email/i);
    const passwordInput = screen.getByLabelText(/password/i);
    expect(emailInput).toBeRequired();
    expect(passwordInput).toBeRequired();
  });

  it("shows error on failed login", async () => {
    const { api } = await import("../src/api/client");
    (api.post as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
      new Error("Invalid credentials"),
    );

    await renderWithProviders(<LoginForm />);
    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/email/i), "test@example.com");
    await user.type(screen.getByLabelText(/password/i), "wrongpassword");
    await user.click(screen.getByRole("button", { name: /login/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid credentials");
  });

  it("calls onSuccess after successful login", async () => {
    const { api } = await import("../src/api/client");
    (api.post as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      id: "123",
      email: "test@example.com",
      is_active: true,
      created_at: new Date().toISOString(),
    });

    const onSuccess = vi.fn();
    await renderWithProviders(<LoginForm onSuccess={onSuccess} />);
    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/email/i), "test@example.com");
    await user.type(screen.getByLabelText(/password/i), "password123");
    await user.click(screen.getByRole("button", { name: /login/i }));

    expect(onSuccess).toHaveBeenCalled();
  });
});
