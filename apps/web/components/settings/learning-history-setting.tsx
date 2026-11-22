"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type SettingsBody = {
  learning_history_limit?: number;
  error?: { message?: string };
};

export function LearningHistorySetting() {
  const [limit, setLimit] = useState("10");
  const [status, setStatus] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const res = await fetch("/api/settings/learning-history", { credentials: "include" });
      const body = (await res.json().catch(() => null)) as SettingsBody | null;
      if (cancelled || !res.ok || typeof body?.learning_history_limit !== "number") return;
      setLimit(String(body.learning_history_limit));
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function save() {
    const value = Number.parseInt(limit, 10);
    if (!Number.isInteger(value) || value < 1 || value > 100) {
      setStatus("Enter a whole number from 1 to 100.");
      return;
    }
    setSaving(true);
    setStatus(null);
    const res = await fetch("/api/settings/learning-history", {
      method: "PUT",
      credentials: "include",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ learning_history_limit: value }),
    });
    const body = (await res.json().catch(() => null)) as SettingsBody | null;
    setSaving(false);
    if (!res.ok) {
      setStatus(body?.error?.message || "Could not save the history limit.");
      return;
    }
    setLimit(String(body?.learning_history_limit ?? value));
    setStatus("Saved. My Library and Recent Learning now keep this many lessons.");
  }

  return (
    <form
      className="space-y-3 rounded-[var(--radius-card)] border border-border bg-surface p-4"
      onSubmit={(event) => {
        event.preventDefault();
        void save();
      }}
    >
      <div className="space-y-2">
        <Label htmlFor="learning-history-limit">Lessons to keep</Label>
        <p className="text-sm text-muted-foreground">
          My Library and Recent Learning share this list. The default is 10. Saving a smaller
          number drops the oldest lessons immediately.
        </p>
        <Input
          id="learning-history-limit"
          name="learning_history_limit"
          type="number"
          min={1}
          max={100}
          inputMode="numeric"
          value={limit}
          onChange={(event) => setLimit(event.target.value)}
        />
      </div>
      <Button type="submit" disabled={saving}>
        {saving ? "Saving…" : "Save history limit"}
      </Button>
      {status ? <p className="text-sm text-muted-foreground">{status}</p> : null}
    </form>
  );
}
