import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { RegisterForm } from "../src/components/RegisterForm";
import { AuthProvider } from "../src/contexts/AuthContext";
import { BrowserRouter } from "react-router-dom";

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
    expect(screen.getByRole("button", { name: /register/i })).toBeInTheDocument();
  });
  return result;
}

describe("RegisterForm", () => {
  it("renders all form fields", async () => {
    await renderWithProviders(<RegisterForm />);
    expect(screen.getByLabelText(/^email$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^password$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/confirm password/i)).toBeInTheDocument();
  });

  it("shows error when passwords do not match", async () => {
    await renderWithProviders(<RegisterForm />);
    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/^email$/i), "new@example.com");
    await user.type(screen.getByLabelText(/^password$/i), "password123");
    await user.type(screen.getByLabelText(/confirm password/i), "different");
    await user.click(screen.getByRole("button", { name: /register/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Passwords do not match",
    );
  });

  it("calls onSuccess after successful registration", async () => {
    const { api } = await import("../src/api/client");
    (api.post as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      id: "123",
      email: "new@example.com",
      is_active: true,
      created_at: new Date().toISOString(),
    });

    const onSuccess = vi.fn();
    await renderWithProviders(<RegisterForm onSuccess={onSuccess} />);
    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/^email$/i), "new@example.com");
    await user.type(screen.getByLabelText(/^password$/i), "password123");
    await user.type(screen.getByLabelText(/confirm password/i), "password123");
    await user.click(screen.getByRole("button", { name: /register/i }));

    expect(onSuccess).toHaveBeenCalled();
  });
});
