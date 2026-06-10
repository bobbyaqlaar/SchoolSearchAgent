import { Suspense } from "react";

import { ComparePageClient } from "@/components/ComparePageClient";
import { Skeleton } from "@/components/ui/Skeleton";

export default function ComparePage(): React.ReactElement {
  return (
    <Suspense
      fallback={
        <div className="space-y-4" role="status" aria-label="Loading compare page">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-10 w-full" />
        </div>
      }
    >
      <ComparePageClient />
    </Suspense>
  );
}
