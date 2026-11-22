"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

type PageTitleContextValue = {
  title: string | null;
  setTitle: (title: string | null) => void;
};

const PageTitleContext = createContext<PageTitleContextValue | null>(null);

export function PageTitleProvider({ children }: { children: ReactNode }) {
  const [title, setTitleState] = useState<string | null>(null);
  const setTitle = useCallback((next: string | null) => {
    setTitleState(next);
  }, []);
  const value = useMemo(() => ({ title, setTitle }), [title, setTitle]);
  return <PageTitleContext.Provider value={value}>{children}</PageTitleContext.Provider>;
}

export function usePageTitleValue(): string | null {
  return useContext(PageTitleContext)?.title ?? null;
}

/** Sets the browser tab title once a lesson title is known. */
export function usePageTitle(title: string | null) {
  const setTitle = useContext(PageTitleContext)?.setTitle;
  useEffect(() => {
    setTitle?.(title);
    if (title) document.title = `${title} · LearnLens AI`;
    return () => setTitle?.(null);
  }, [setTitle, title]);
}
