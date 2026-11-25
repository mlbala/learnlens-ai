"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";

type MeBody = {
  user?: { email?: string; display_name?: string | null };
  workspace?: { name?: string };
};

type Session =
  | { state: "signed_in"; email: string; workspaceName: string }
  | { state: "signed_out" }
  | { state: "unavailable" };

export const meQueryKey = ["me"] as const;

async function loadSession(): Promise<Session> {
  const res = await fetch("/api/me", { credentials: "include", cache: "no-store" });
  if (res.status === 401) return { state: "signed_out" };
  if (!res.ok) return { state: "unavailable" };
  const body = (await res.json().catch(() => null)) as MeBody | null;
  const email = body?.user?.email;
  if (!email) return { state: "unavailable" };
  return { state: "signed_in", email, workspaceName: body?.workspace?.name ?? "" };
}

/** Who is signed in, from GET /api/v1/me. Local login only; no registration form. */
export function AccountStatus() {
  const queryClient = useQueryClient();
  const [busy, setBusy] = useState(false);
  const query = useQuery({ queryKey: meQueryKey, queryFn: loadSession, retry: false });
  const session = query.data;

  async function run(path: string) {
    setBusy(true);
    await fetch(path, { method: "POST", credentials: "include" }).catch(() => null);
    setBusy(false);
    // Every cached library view belongs to the old session.
    await queryClient.invalidateQueries();
  }

  if (!session || session.state === "unavailable") return null;

  if (session.state === "signed_out") {
    return (
      <div className="flex shrink-0 items-center gap-2 text-xs">
        <span className="text-muted-foreground">Signed out</span>
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={busy}
          onClick={() => void run("/api/auth/sign-in")}
        >
          Sign in again
        </Button>
      </div>
    );
  }

  return (
    <div className="flex min-w-0 shrink-0 items-center gap-2 text-xs">
      <div className="hidden min-w-0 flex-col leading-tight md:flex" title={session.email}>
        <span className="max-w-[12rem] truncate font-medium text-foreground">{session.email}</span>
        {session.workspaceName ? (
          <span className="max-w-[12rem] truncate text-muted-foreground">
            {session.workspaceName}
          </span>
        ) : null}
      </div>
      <Button
        type="button"
        size="sm"
        variant="outline"
        disabled={busy}
        onClick={() => void run("/api/auth/logout")}
      >
        Sign out
      </Button>
    </div>
  );
}
