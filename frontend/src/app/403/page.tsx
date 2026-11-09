import Link from "next/link";

import { BrandMark } from "@/components/brand";
import { Button } from "@/components/ui/button";

export default function ForbiddenPage() {
  return (
    <main className="flex min-h-svh flex-col items-center justify-center gap-6 px-6 text-center">
      <BrandMark />
      <div className="space-y-2">
        <p className="text-sm font-semibold text-muted-foreground">403</p>
        <h1 className="text-2xl font-semibold tracking-tight">
          You do not have access to this page
        </h1>
        <p className="max-w-md text-sm text-muted-foreground">
          This area is limited to administrators. If you believe you should have
          access, contact your platform administrator.
        </p>
      </div>
      <Button asChild>
        <Link href="/departments">Back to departments</Link>
      </Button>
    </main>
  );
}
