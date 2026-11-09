"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowRight, Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { BrandMark } from "@/components/brand";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiRequestError, api } from "@/lib/api";
import type { TokenResponse, User } from "@/lib/types";

const schema = z.object({
  email: z.email("Enter a valid email address"),
  password: z.string().min(1, "Enter your password"),
});

type Values = z.infer<typeof schema>;

export default function LoginPage() {
  const router = useRouter();

  // If a live session already exists, skip the form. This replaces a middleware
  // redirect, which could loop when the access cookie outlived a revoked refresh token.
  const session = useQuery({
    // A separate key from the shell's ["session"]: a pre-login 401 must not be
    // mistaken for the authenticated shell's session state.
    queryKey: ["session", "probe"],
    queryFn: () => api.get<User>("/api/v1/auth/me"),
    retry: false,
  });

  useEffect(() => {
    if (!session.data) return;
    if (session.data.must_change_password) {
      router.replace("/change-password");
    } else {
      router.replace(session.data.role === "ADMIN" ? "/departments" : "/403");
    }
  }, [session.data, router]);

  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { email: "", password: "" },
  });

  const mutation = useMutation({
    mutationFn: (values: Values) =>
      api.post<TokenResponse>("/api/v1/auth/login", values),
    onSuccess: (data) => {
      if (data.user.must_change_password) {
        router.replace("/change-password");
        return;
      }
      const isAdmin = data.user.role === "ADMIN";
      const fallback = isAdmin ? "/departments" : "/403";
      const next = new URLSearchParams(window.location.search).get("next");
      const allowed = isAdmin && next && next.startsWith("/");
      router.replace(allowed ? next : fallback);
    },
    onError: (error) => {
      toast.error(
        error instanceof ApiRequestError
          ? error.message
          : "Unable to sign in. Try again.",
      );
    },
  });

  return (
    <main className="relative flex min-h-svh items-center justify-center overflow-hidden bg-background px-6 py-12">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(60%_50%_at_50%_0%,color-mix(in_oklch,var(--primary)_12%,transparent),transparent)]"
      />
      <div className="relative w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center gap-4 text-center">
          <BrandMark />
          <div className="space-y-1.5">
            <h1 className="text-2xl font-semibold tracking-tight">
              Sign in to your workspace
            </h1>
            <p className="text-sm text-muted-foreground">
              Accounts are created by your administrator.
            </p>
          </div>
        </div>

        <Card className="shadow-lg shadow-black/5">
          <CardHeader className="sr-only">
            <CardTitle>Sign in</CardTitle>
            <CardDescription>
              Use your organisation credentials.
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-6">
            <form
              className="space-y-5"
              onSubmit={form.handleSubmit((values) => mutation.mutate(values))}
              noValidate
            >
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  autoComplete="username"
                  placeholder="you@company.com"
                  aria-invalid={Boolean(form.formState.errors.email)}
                  {...form.register("email")}
                />
                {form.formState.errors.email ? (
                  <p className="text-xs text-destructive">
                    {form.formState.errors.email.message}
                  </p>
                ) : null}
              </div>

              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  placeholder="••••••••••••"
                  aria-invalid={Boolean(form.formState.errors.password)}
                  {...form.register("password")}
                />
                {form.formState.errors.password ? (
                  <p className="text-xs text-destructive">
                    {form.formState.errors.password.message}
                  </p>
                ) : null}
              </div>

              <Button
                type="submit"
                className="w-full"
                disabled={mutation.isPending}
              >
                {mutation.isPending ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : null}
                Sign in
                {!mutation.isPending ? <ArrowRight className="size-4" /> : null}
              </Button>
            </form>
          </CardContent>
        </Card>

        <p className="mt-6 text-center text-xs text-muted-foreground">
          Need access? Contact your platform administrator.
        </p>
      </div>
    </main>
  );
}
