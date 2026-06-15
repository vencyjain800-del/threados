"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { auth } from "@/lib/api-client";

interface AppNavProps {
  activePath: "dashboard" | "inventory" | "settings";
}

export function AppNav({ activePath }: AppNavProps) {
  const router = useRouter();

  const handleSignOut = async () => {
    await auth.logout().catch(() => null);
    router.push("/login");
  };

  const linkClass = (path: AppNavProps["activePath"]) =>
    activePath === path
      ? "text-sm text-brand-600 font-medium"
      : "text-sm text-gray-600 hover:text-gray-900";

  return (
    <nav className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between">
      <div className="flex items-center gap-6">
        <span className="text-lg font-bold text-brand-700">ThreadOS</span>
        <div className="flex items-center gap-5">
          <Link href="/dashboard" className={linkClass("dashboard")}>
            Dashboard
          </Link>
          <Link href="/inventory" className={linkClass("inventory")}>
            Inventory
          </Link>
        </div>
      </div>
      <div className="flex items-center gap-4">
        <Link href="/settings" className={linkClass("settings")}>
          Settings
        </Link>
        <button
          onClick={() => {
            void handleSignOut();
          }}
          className="text-sm text-gray-500 hover:text-gray-700"
        >
          Sign out
        </button>
      </div>
    </nav>
  );
}
