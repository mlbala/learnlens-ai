"use client";

import { LayoutGrid, List } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

export type LibraryViewMode = "grid" | "list";
export type LibraryStatusFilter =
  | "all"
  | "ready"
  | "needs_transcript"
  | "processing"
  | "failed";

type LibraryToolbarProps = {
  view: LibraryViewMode;
  onViewChange: (view: LibraryViewMode) => void;
  status: LibraryStatusFilter;
  onStatusChange: (status: LibraryStatusFilter) => void;
  query: string;
  onQueryChange: (query: string) => void;
  idPrefix?: string;
};

const STATUS_OPTIONS: { value: LibraryStatusFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "ready", label: "Ready" },
  { value: "needs_transcript", label: "Needs transcript" },
  { value: "processing", label: "Processing" },
  { value: "failed", label: "Failed" },
];

export function LibraryToolbar({
  view,
  onViewChange,
  status,
  onStatusChange,
  query,
  onQueryChange,
  idPrefix = "library",
}: LibraryToolbarProps) {
  const searchId = `${idPrefix}-search`;
  const statusId = `${idPrefix}-status`;

  return (
    <div className="mb-6 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
      <div className="flex flex-1 flex-col gap-3 sm:flex-row sm:items-end">
        <div className="min-w-0 flex-1 space-y-1.5">
          <Label htmlFor={searchId}>Search titles</Label>
          <Input
            id={searchId}
            type="search"
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
            placeholder="Search by title"
            autoComplete="off"
          />
        </div>
        <div className="space-y-1.5 sm:w-52">
          <Label htmlFor={statusId}>Status</Label>
          <select
            id={statusId}
            className="flex h-11 w-full rounded-[var(--radius-control)] border border-border bg-surface px-3 text-sm"
            value={status}
            onChange={(e) => onStatusChange(e.target.value as LibraryStatusFilter)}
          >
            {STATUS_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      </div>
      <div
        className="flex items-center gap-1 rounded-[var(--radius-control)] border border-border p-1"
        role="group"
        aria-label="Library layout"
      >
        <Button
          type="button"
          size="icon"
          variant={view === "grid" ? "secondary" : "ghost"}
          aria-pressed={view === "grid"}
          aria-label="Grid view"
          onClick={() => onViewChange("grid")}
          className={cn(view === "grid" && "bg-surface-muted")}
        >
          <LayoutGrid />
        </Button>
        <Button
          type="button"
          size="icon"
          variant={view === "list" ? "secondary" : "ghost"}
          aria-pressed={view === "list"}
          aria-label="List view"
          onClick={() => onViewChange("list")}
          className={cn(view === "list" && "bg-surface-muted")}
        >
          <List />
        </Button>
      </div>
    </div>
  );
}
