import { Suspense } from "react";

import { LibraryBrowser } from "@/components/library/library-browser";

export const metadata = { title: "My Library" };

export default function LibraryPage() {
  return (
    <Suspense>
      <LibraryBrowser />
    </Suspense>
  );
}
