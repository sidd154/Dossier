"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Building2,
  Database,
  LogOut,
  Mail,
  Settings2,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { BrandMark } from "@/components/brand";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiRequestError, api } from "@/lib/api";
import { initials } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { User } from "@/lib/types";

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  exact?: boolean;
  soon?: boolean;
}

const NAVIGATION: NavItem[] = [
  { href: "/departments", label: "Departments", icon: Building2 },
  { href: "/data", label: "Data", icon: Database },
  { href: "/mail", label: "Mail", icon: Mail },
  { href: "/settings", label: "Settings", icon: Settings2 },
];

export function useSession() {
  return useQuery({
    queryKey: ["session"],
    queryFn: () => api.get<User>("/api/v1/auth/me"),
    retry: false,
  });
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const queryClient = useQueryClient();
  const session = useSession();

  useEffect(() => {
    if (
      session.error instanceof ApiRequestError &&
      session.error.status === 401
    ) {
      router.replace("/login");
    }
  }, [session.error, router]);

  useEffect(() => {
    if (session.data?.must_change_password) {
      router.replace("/change-password");
    }
  }, [session.data, router]);

  const signOut = async () => {
    await api.post("/api/v1/auth/logout").catch(() => undefined);
    queryClient.clear();
    router.replace("/login");
  };

  if (session.isLoading) {
    return <ShellSkeleton />;
  }

  if (!session.data) {
    return null;
  }

  const user = session.data;

  if (user.role !== "ADMIN") {
    return (
      <main className="flex min-h-svh flex-col items-center justify-center gap-5 px-6 text-center">
        <BrandMark />
        <div className="space-y-1.5">
          <h1 className="text-2xl font-semibold tracking-tight">
            Access is limited to administrators
          </h1>
          <p className="max-w-md text-sm text-muted-foreground">
            Your account is a mail recipient. There is no user-facing interface
            in this version.
          </p>
        </div>
        <Button variant="outline" onClick={signOut}>
          Sign out
        </Button>
      </main>
    );
  }

  const navigation = NAVIGATION;

  return (
    <div className="min-h-svh bg-background">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 flex-col border-r bg-sidebar lg:flex">
        <div className="flex h-16 items-center px-5">
          <BrandMark />
        </div>
        <Separator />
        <nav className="flex-1 space-y-1 overflow-y-auto p-3">
          {navigation.map((item) => (
            <NavLink
              key={item.href}
              item={item}
              active={
                item.exact
                  ? pathname === item.href
                  : pathname === item.href ||
                    pathname.startsWith(`${item.href}/`)
              }
            />
          ))}
        </nav>
        <div className="border-t p-3">
          <UserMenu user={user} onSignOut={signOut} />
        </div>
      </aside>

      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 flex h-16 items-center justify-between gap-3 border-b bg-background/85 px-4 backdrop-blur-md sm:px-6 lg:px-8">
          <div className="flex items-center gap-3 lg:hidden">
            <BrandMark compact />
            <MobileNav pathname={pathname} items={navigation} />
          </div>
          <div className="hidden lg:block">
            <p className="text-sm font-medium">
              {navigation.find((item) =>
                item.exact
                  ? pathname === item.href
                  : pathname === item.href ||
                    pathname.startsWith(`${item.href}/`),
              )?.label ?? "Workspace"}
            </p>
            <p className="text-xs text-muted-foreground">
              {user.department?.name ?? "No department"}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="secondary" className="hidden sm:inline-flex">
              {user.role === "ADMIN" ? "Administrator" : "Member"}
            </Badge>
            <div className="lg:hidden">
              <UserMenu user={user} onSignOut={signOut} compact />
            </div>
          </div>
        </header>

        <main className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 sm:py-8 lg:px-8">
          {children}
        </main>
      </div>
    </div>
  );
}

function NavLink({
  item,
  active,
}: {
  item: (typeof NAVIGATION)[number];
  active: boolean;
}) {
  const Icon = item.icon;
  const content = (
    <span
      className={cn(
        "group flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
        active
          ? "bg-sidebar-accent text-sidebar-accent-foreground"
          : "text-muted-foreground hover:bg-sidebar-accent/60 hover:text-foreground",
      )}
    >
      <Icon className="size-4 shrink-0" />
      <span className="flex-1 truncate">{item.label}</span>
      {item.soon ? (
        <span className="rounded-full bg-muted px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
          Soon
        </span>
      ) : null}
    </span>
  );

  if (item.soon) {
    return <div className="cursor-not-allowed opacity-70">{content}</div>;
  }

  return (
    <Link href={item.href} aria-current={active ? "page" : undefined}>
      {content}
    </Link>
  );
}

function MobileNav({
  pathname,
  items,
}: {
  pathname: string;
  items: NavItem[];
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm">
          Menu
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-56">
        {items.map((item) => (
          <DropdownMenuItem key={item.href} asChild disabled={item.soon}>
            <Link href={item.href}>
              <item.icon className="size-4" />
              {item.label}
              {pathname === item.href ||
              pathname.startsWith(`${item.href}/`) ? (
                <span className="ml-auto text-xs text-muted-foreground">
                  Here
                </span>
              ) : null}
            </Link>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function UserMenu({
  user,
  onSignOut,
  compact = false,
}: {
  user: User;
  onSignOut: () => void;
  compact?: boolean;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          className={cn(
            "h-auto w-full justify-start gap-3 px-2 py-2",
            compact && "w-auto px-1",
          )}
        >
          <Avatar className="size-8">
            <AvatarFallback className="text-xs font-semibold">
              {initials(user.full_name)}
            </AvatarFallback>
          </Avatar>
          {!compact ? (
            <span className="min-w-0 flex-1 text-left">
              <span className="block truncate text-sm font-medium">
                {user.full_name}
              </span>
              <span className="block truncate text-xs text-muted-foreground">
                {user.email}
              </span>
            </span>
          ) : null}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel>
          <span className="block text-sm font-medium">{user.full_name}</span>
          <span className="block text-xs font-normal text-muted-foreground">
            {user.email}
          </span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link href="/change-password">Change password</Link>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={onSignOut}>
          <LogOut className="size-4" />
          Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function ShellSkeleton() {
  return (
    <div className="min-h-svh bg-background">
      <aside className="fixed inset-y-0 left-0 hidden w-64 flex-col border-r p-5 lg:flex">
        <Skeleton className="h-9 w-32" />
        <div className="mt-8 space-y-2">
          {Array.from({ length: 6 }).map((_, index) => (
            <Skeleton key={index} className="h-9 w-full" />
          ))}
        </div>
      </aside>
      <div className="lg:pl-64">
        <header className="flex h-16 items-center border-b px-6">
          <Skeleton className="h-5 w-40" />
        </header>
        <main className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
          <Skeleton className="h-8 w-56" />
          <div className="mt-6 grid gap-4 sm:grid-cols-3">
            {Array.from({ length: 3 }).map((_, index) => (
              <Skeleton key={index} className="h-28 w-full" />
            ))}
          </div>
          <Skeleton className="mt-6 h-72 w-full" />
        </main>
      </div>
    </div>
  );
}
