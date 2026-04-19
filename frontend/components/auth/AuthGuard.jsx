"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "./AuthProvider";

export default function AuthGuard({ children }) {
  const router = useRouter();
  const pathname = usePathname();
  const { isAuthenticated, ready } = useAuth();

  useEffect(() => {
    if (ready && !isAuthenticated) {
      router.replace(`/login?next=${encodeURIComponent(pathname || "/workspace")}`);
    }
  }, [isAuthenticated, pathname, ready, router]);

  if (!ready || !isAuthenticated) {
    return (
      <div className="mx-auto mt-28 w-full max-w-md px-4">
        <div className="glass-panel rounded-2xl p-6 text-center">
          <p className="text-sm text-slate-300">Preparing your campaign workspace...</p>
        </div>
      </div>
    );
  }

  return children;
}
