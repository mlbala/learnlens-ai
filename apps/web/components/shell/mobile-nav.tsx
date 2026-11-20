"use client";

import { Menu } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { SidebarNav } from "@/components/shell/sidebar-nav";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

export function MobileNav() {
  const [open, setOpen] = useState(false);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button
          type="button"
          variant="outline"
          size="icon"
          className="lg:hidden"
          aria-label="Open navigation menu"
        >
          <Menu className="h-4 w-4" />
        </Button>
      </DialogTrigger>
      <DialogContent className="left-0 top-0 h-full max-h-none w-[min(100%,20rem)] max-w-none translate-x-0 translate-y-0 rounded-none border-y-0 border-l-0 p-0 sm:rounded-none">
        <DialogHeader className="border-b border-border px-5 py-4 text-left">
          <DialogTitle>
            <Link href="/" onClick={() => setOpen(false)}>
              LearnLens <span className="text-primary">AI</span>
            </Link>
          </DialogTitle>
          <DialogDescription className="sr-only">
            Primary application navigation
          </DialogDescription>
        </DialogHeader>
        <div className="px-3 py-4">
          <SidebarNav onNavigate={() => setOpen(false)} />
        </div>
      </DialogContent>
    </Dialog>
  );
}
