"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { KeyRound, Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
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
import type { TokenResponse } from "@/lib/types";

const schema = z
  .object({
    current_password: z.string().min(1, "Enter your current password"),
    new_password: z
      .string()
      .min(12, "Use at least 12 characters")
      .max(128, "Use at most 128 characters"),
    confirm_password: z.string().min(1, "Repeat the new password"),
  })
  .refine((values) => values.new_password === values.confirm_password, {
    path: ["confirm_password"],
    message: "Passwords do not match",
  })
  .refine((values) => values.new_password !== values.current_password, {
    path: ["new_password"],
    message: "Choose a different password",
  });

type Values = z.infer<typeof schema>;

export default function ChangePasswordPage() {
  const router = useRouter();
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      current_password: "",
      new_password: "",
      confirm_password: "",
    },
  });

  const mutation = useMutation({
    mutationFn: (values: Values) =>
      api.post<TokenResponse>("/api/v1/auth/change-password", {
        current_password: values.current_password,
        new_password: values.new_password,
      }),
    onSuccess: (data) => {
      toast.success("Password updated");
      router.replace(data.user.role === "ADMIN" ? "/departments" : "/403");
    },
    onError: (error) => {
      toast.error(
        error instanceof ApiRequestError
          ? error.message
          : "Could not update your password.",
      );
    },
  });

  const errorFor = (field: keyof Values) =>
    form.formState.errors[field]?.message;

  return (
    <main className="relative flex min-h-svh items-center justify-center overflow-hidden bg-background px-6 py-12">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(60%_50%_at_50%_0%,color-mix(in_oklch,var(--primary)_12%,transparent),transparent)]"
      />
      <div className="relative w-full max-w-md">
        <div className="mb-8 flex flex-col items-center gap-4 text-center">
          <BrandMark />
          <div className="space-y-1.5">
            <h1 className="text-2xl font-semibold tracking-tight">
              Set a new password
            </h1>
            <p className="text-sm text-muted-foreground">
              Your administrator issued a temporary password. Replace it to
              continue.
            </p>
          </div>
        </div>

        <Card className="shadow-lg shadow-black/5">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <KeyRound className="size-4 text-muted-foreground" />
              Password
            </CardTitle>
            <CardDescription>
              At least 12 characters. A passphrase is ideal.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form
              className="space-y-4"
              onSubmit={form.handleSubmit((values) => mutation.mutate(values))}
              noValidate
            >
              <div className="space-y-2">
                <Label htmlFor="current_password">Temporary password</Label>
                <Input
                  id="current_password"
                  type="password"
                  autoComplete="current-password"
                  aria-invalid={Boolean(errorFor("current_password"))}
                  {...form.register("current_password")}
                />
                {errorFor("current_password") ? (
                  <p className="text-xs text-destructive">
                    {errorFor("current_password")}
                  </p>
                ) : null}
              </div>

              <div className="space-y-2">
                <Label htmlFor="new_password">New password</Label>
                <Input
                  id="new_password"
                  type="password"
                  autoComplete="new-password"
                  aria-invalid={Boolean(errorFor("new_password"))}
                  {...form.register("new_password")}
                />
                {errorFor("new_password") ? (
                  <p className="text-xs text-destructive">
                    {errorFor("new_password")}
                  </p>
                ) : null}
              </div>

              <div className="space-y-2">
                <Label htmlFor="confirm_password">Confirm new password</Label>
                <Input
                  id="confirm_password"
                  type="password"
                  autoComplete="new-password"
                  aria-invalid={Boolean(errorFor("confirm_password"))}
                  {...form.register("confirm_password")}
                />
                {errorFor("confirm_password") ? (
                  <p className="text-xs text-destructive">
                    {errorFor("confirm_password")}
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
                Update password
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
