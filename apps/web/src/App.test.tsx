import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Session } from "@supabase/supabase-js";
import type { ReactElement } from "react";
import App from "./App";

function renderApp(ui: ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

const { mockState, fromMock, rpcMock } = vi.hoisted(() => {
  const mockState = {
    session: null as Session | null,
    rpcError: null as { message: string } | null,
    rpcOrgId: "11111111-1111-1111-1111-111111111111" as string | null,
    membershipOrgIds: [] as string[],
  };
  const fromMock = vi.fn();
  const rpcMock = vi.fn((name: string) => {
    if (name === "create_organization") {
      if (mockState.rpcError) {
        return Promise.resolve({ data: null, error: mockState.rpcError });
      }
      if (mockState.rpcOrgId) {
        mockState.membershipOrgIds = [mockState.rpcOrgId];
      }
      return Promise.resolve({ data: mockState.rpcOrgId, error: null });
    }
    return Promise.resolve({ data: null, error: { message: `unmocked rpc ${name}` } });
  });
  return { mockState, fromMock, rpcMock };
});

vi.mock("./supabaseClient", () => ({
  supabase: {
    auth: {
      getSession: () => Promise.resolve({ data: { session: mockState.session } }),
      onAuthStateChange: (cb: (event: string, session: Session | null) => void) => {
        queueMicrotask(() => cb("INITIAL_SESSION", mockState.session));
        return { data: { subscription: { unsubscribe: vi.fn() } } };
      },
      signInWithPassword: vi.fn().mockResolvedValue({ error: null }),
      signUp: vi.fn().mockResolvedValue({ error: null }),
      signOut: vi.fn().mockResolvedValue({ error: null }),
    },
    from: fromMock,
    rpc: rpcMock,
    functions: {
      invoke: vi.fn().mockResolvedValue({ data: null, error: null }),
    },
  },
}));

function minimalSession(): Session {
  return {
    access_token: "t",
    refresh_token: "r",
    expires_in: 3600,
    expires_at: Math.floor(Date.now() / 1000) + 3600,
    token_type: "bearer",
    user: {
      id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
      aud: "authenticated",
      role: "authenticated",
      email: "u@test.local",
      app_metadata: {},
      user_metadata: {},
      created_at: new Date().toISOString(),
    },
  } as Session;
}

describe("App UI", () => {
  beforeEach(() => {
    mockState.session = null;
    mockState.rpcError = null;
    mockState.rpcOrgId = "11111111-1111-1111-1111-111111111111";
    mockState.membershipOrgIds = [];
    fromMock.mockReset();
    rpcMock.mockClear();
    fromMock.mockImplementation((table: string) => {
      if (table === "organization_members") {
        return {
          select: () => ({
            eq: () =>
              Promise.resolve({
                data: mockState.membershipOrgIds.map((id) => ({ organization_id: id })),
                error: null,
              }),
          }),
        };
      }
      if (table === "organizations") {
        return {
          select: () => ({
            in: () =>
              Promise.resolve({
                data: mockState.membershipOrgIds.map((id) => ({
                  id,
                  name: "Acme Corp",
                  slug: "acme",
                })),
                error: null,
              }),
          }),
        };
      }
      if (table === "step_type_catalog") {
        return {
          select: () => Promise.resolve({ data: [], error: null }),
        };
      }
      if (table === "projects") {
        return {
          select: () => ({
            eq: () => Promise.resolve({ data: [], error: null }),
            in: () => Promise.resolve({ data: [], error: null }),
          }),
        };
      }
      if (table === "config_branches") {
        return {
          select: () => ({
            eq: () => Promise.resolve({ data: [], error: null }),
          }),
        };
      }
      if (table === "config_revisions") {
        return {
          select: () => ({
            eq: () => ({
              order: () => ({
                limit: () => ({
                  maybeSingle: () => Promise.resolve({ data: null, error: null }),
                }),
              }),
            }),
          }),
        };
      }
      return {
        select: () => Promise.resolve({ data: null, error: null }),
      };
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("shows sign-in when there is no session", async () => {
    mockState.session = null;
    renderApp(<App />);
    expect(await screen.findByRole("heading", { name: /Wurzel KaaS/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Sign in$/i })).toBeInTheDocument();
  });

  it("shows create organization form when signed in without an org", async () => {
    mockState.session = minimalSession();
    renderApp(<App />);
    expect(await screen.findByRole("heading", { name: /Create your organization/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/organization name/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Create organization/i })).toBeInTheDocument();
  });

  it("displays Supabase error when create organization RPC fails", async () => {
    const user = userEvent.setup();
    mockState.session = minimalSession();
    mockState.rpcError = { message: 'new row violates row-level security policy for table "organizations"' };
    renderApp(<App />);
    await screen.findByRole("heading", { name: /Create your organization/i });
    await user.type(screen.getByLabelText(/organization name/i), "Acme");
    await user.click(screen.getByRole("button", { name: /Create organization/i }));
    await waitFor(() => {
      expect(screen.getByText(/row-level security policy/i)).toBeInTheDocument();
    });
  });

  it("advances to create project after organization is created", async () => {
    const user = userEvent.setup();
    mockState.session = minimalSession();
    mockState.rpcError = null;
    renderApp(<App />);
    await screen.findByRole("heading", { name: /Create your organization/i });
    await user.type(screen.getByLabelText(/organization name/i), "Acme");
    await user.click(screen.getByRole("button", { name: /Create organization/i }));
    expect(await screen.findByRole("heading", { name: /^Projects$/i })).toBeInTheDocument();
  });
});
