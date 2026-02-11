export interface ApiError {
  detail: string;
}

class ApiClient {
  private baseUrl: string;
  private refreshPromise: Promise<boolean> | null = null;

  constructor(baseUrl = "") {
    this.baseUrl = baseUrl;
  }

  private async refreshToken(): Promise<boolean> {
    if (this.refreshPromise) return this.refreshPromise;

    this.refreshPromise = (async () => {
      try {
        const resp = await fetch(`${this.baseUrl}/api/v1/auth/refresh`, {
          method: "POST",
          credentials: "same-origin",
        });
        return resp.ok;
      } finally {
        this.refreshPromise = null;
      }
    })();

    return this.refreshPromise;
  }

  private async parseJson<T>(response: Response): Promise<T> {
    const contentType = response.headers.get("content-type");
    if (!contentType?.includes("application/json")) {
      throw new ApiRequestError(
        response.status,
        `Expected JSON response, got ${contentType ?? "unknown"}`,
      );
    }
    return response.json() as Promise<T>;
  }

  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const init: RequestInit = {
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
      },
      ...options,
    };

    const response = await fetch(`${this.baseUrl}${path}`, init);

    if (response.status === 401 && !path.includes("/auth/refresh")) {
      const refreshed = await this.refreshToken();

      if (refreshed) {
        // Retry original request
        const retryResp = await fetch(`${this.baseUrl}${path}`, init);

        if (retryResp.ok) {
          return this.parseJson<T>(retryResp);
        }

        // Retry failed for non-auth reason — surface the real error
        if (retryResp.status !== 401) {
          const body = await retryResp
            .json()
            .catch(() => ({ detail: "Request failed" }));
          throw new ApiRequestError(
            retryResp.status,
            body.detail ?? "Request failed",
          );
        }
      }

      // Refresh failed or retry still 401
      throw new AuthError("Session expired");
    }

    if (!response.ok) {
      const body = await response
        .json()
        .catch(() => ({ detail: "Request failed" }));
      throw new ApiRequestError(response.status, body.detail ?? "Request failed");
    }

    return this.parseJson<T>(response);
  }

  get<T>(path: string): Promise<T> {
    return this.request<T>(path);
  }

  post<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>(path, {
      method: "POST",
      body: body ? JSON.stringify(body) : undefined,
    });
  }
}

export class AuthError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "AuthError";
  }
}

export class ApiRequestError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiRequestError";
  }
}

export const api = new ApiClient();
