"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Loader2, Mail, Send, ShieldAlert } from "lucide-react";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { PageHeader } from "@/components/page-header";
import { ErrorState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiRequestError, api } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { MailSettings, MailTestResult } from "@/lib/types";

const schema = z.object({
  host: z.string().min(1, "Enter the SMTP host"),
  port: z.number().int().min(1, "Port must be 1-65535").max(65535),
  from_email: z.email("Enter a valid sender address"),
  from_name: z.string().optional(),
  username: z.string().optional(),
  password: z.string().optional(),
  security: z.enum(["NONE", "STARTTLS", "SSL"]),
  clear_password: z.boolean(),
  test_to: z.string().optional(),
});

type Values = z.infer<typeof schema>;

export default function MailSettingsPage() {
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: ["mail-settings"],
    queryFn: async () => {
      try {
        return await api.get<MailSettings>("/api/v1/admin/mail/settings");
      } catch (error) {
        if (error instanceof ApiRequestError && error.status === 404)
          return null;
        throw error;
      }
    },
  });

  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      host: "",
      port: 1025,
      from_email: "",
      from_name: "",
      username: "",
      password: "",
      security: "NONE",
      clear_password: false,
      test_to: "",
    },
  });

  useEffect(() => {
    if (!query.isFetched) return;
    const settings = query.data;
    form.reset({
      host: settings?.host ?? "",
      port: settings?.port ?? 1025,
      from_email: settings?.from_email ?? "",
      from_name: settings?.from_name ?? "",
      username: settings?.username ?? "",
      password: "",
      security: settings?.security ?? "NONE",
      clear_password: false,
      test_to: form.getValues("test_to") ?? "",
    });
  }, [query.data, query.isFetched, form]);

  const save = useMutation({
    mutationFn: (values: Values) =>
      api.patch<MailSettings>("/api/v1/admin/mail/settings", {
        host: values.host.trim(),
        port: values.port,
        from_email: values.from_email.trim(),
        from_name: values.from_name?.trim() || null,
        username: values.username?.trim() || null,
        security: values.security,
        ...(values.password ? { password: values.password } : {}),
        clear_password: values.clear_password,
      }),
    onSuccess: (settings) => {
      queryClient.setQueryData(["mail-settings"], settings);
      form.setValue("password", "");
      form.setValue("clear_password", false);
      toast.success("SMTP settings saved");
    },
    onError: (error) => {
      toast.error(
        error instanceof ApiRequestError
          ? error.message
          : "Could not save SMTP settings.",
      );
    },
  });

  const test = useMutation({
    mutationFn: (to: string) =>
      api.post<MailTestResult>("/api/v1/admin/mail/settings/test", { to }),
    onSuccess: (result) => {
      if (result.ok) {
        toast.success("Test email sent");
      } else {
        toast.error(result.error ?? "Test email failed");
      }
      void queryClient.invalidateQueries({ queryKey: ["mail-settings"] });
    },
    onError: (error) => {
      toast.error(
        error instanceof ApiRequestError
          ? error.message
          : "Could not send the test email.",
      );
    },
  });

  const errorFor = (field: keyof Values) =>
    form.formState.errors[field]?.message;

  if (query.isError) {
    return (
      <Card>
        <ErrorState
          message={
            query.error instanceof ApiRequestError
              ? query.error.message
              : "Could not load mail settings."
          }
          onRetry={() => void query.refetch()}
        />
      </Card>
    );
  }

  return (
    <div>
      <PageHeader
        title="Mail settings"
        description="SMTP credentials used to send scheduled emails. The password is encrypted and never shown again."
        actions={
          query.data ? (
            <Badge variant={query.data.has_password ? "outline" : "secondary"}>
              {query.data.has_password ? "Password stored" : "No password"}
            </Badge>
          ) : (
            <Badge variant="secondary">Not configured</Badge>
          )
        }
      />

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Mail className="size-4 text-muted-foreground" />
              SMTP server
            </CardTitle>
            <CardDescription>
              Development default: host <code>mailhog</code>, port{" "}
              <code>1025</code>, security <code>NONE</code>.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {query.isLoading ? (
              <div className="space-y-4">
                {Array.from({ length: 5 }).map((_, index) => (
                  <Skeleton key={index} className="h-10 w-full" />
                ))}
              </div>
            ) : (
              <form
                className="space-y-5"
                onSubmit={form.handleSubmit((values) => save.mutate(values))}
                noValidate
              >
                <div className="grid gap-4 sm:grid-cols-3">
                  <div className="space-y-2 sm:col-span-2">
                    <Label htmlFor="host">Host</Label>
                    <Input
                      id="host"
                      placeholder="mailhog"
                      {...form.register("host")}
                    />
                    {errorFor("host") ? (
                      <p className="text-xs text-destructive">
                        {errorFor("host")}
                      </p>
                    ) : null}
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="port">Port</Label>
                    <Input
                      id="port"
                      type="number"
                      {...form.register("port", { valueAsNumber: true })}
                    />
                    {errorFor("port") ? (
                      <p className="text-xs text-destructive">
                        {errorFor("port")}
                      </p>
                    ) : null}
                  </div>
                </div>

                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label>Security</Label>
                    <Select
                      value={form.watch("security")}
                      onValueChange={(value) =>
                        form.setValue("security", value as Values["security"])
                      }
                    >
                      <SelectTrigger className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="NONE">None (development)</SelectItem>
                        <SelectItem value="STARTTLS">STARTTLS</SelectItem>
                        <SelectItem value="SSL">SSL</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="username">Username</Label>
                    <Input
                      id="username"
                      autoComplete="off"
                      {...form.register("username")}
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="password">
                    Password{" "}
                    {query.data?.has_password ? "(leave blank to keep)" : ""}
                  </Label>
                  <Input
                    id="password"
                    type="password"
                    autoComplete="new-password"
                    {...form.register("password")}
                  />
                  {query.data?.has_password ? (
                    <label className="flex items-center gap-2 text-xs text-muted-foreground">
                      <input
                        type="checkbox"
                        className="size-3.5 rounded border-input accent-primary"
                        {...form.register("clear_password")}
                      />
                      Remove the stored password
                    </label>
                  ) : null}
                </div>

                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="from_name">From name</Label>
                    <Input id="from_name" {...form.register("from_name")} />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="from_email">From address</Label>
                    <Input
                      id="from_email"
                      type="email"
                      placeholder="noreply@example.com"
                      {...form.register("from_email")}
                    />
                    {errorFor("from_email") ? (
                      <p className="text-xs text-destructive">
                        {errorFor("from_email")}
                      </p>
                    ) : null}
                  </div>
                </div>

                <div className="flex items-center justify-between gap-3 border-t pt-4">
                  <p className="text-xs text-muted-foreground">
                    {query.data
                      ? `Last updated ${formatDateTime(query.data.updated_at)}`
                      : "No SMTP configuration yet"}
                  </p>
                  <Button type="submit" disabled={save.isPending}>
                    {save.isPending ? (
                      <Loader2 className="size-4 animate-spin" />
                    ) : null}
                    Save settings
                  </Button>
                </div>
              </form>
            )}
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Send className="size-4 text-muted-foreground" />
                Test delivery
              </CardTitle>
              <CardDescription>
                Sends a plain test message using the saved settings.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="space-y-2">
                <Label htmlFor="test_to">Recipient</Label>
                <Input
                  id="test_to"
                  type="email"
                  placeholder="you@example.com"
                  {...form.register("test_to")}
                />
              </div>
              <Button
                type="button"
                variant="outline"
                className="w-full"
                disabled={test.isPending || !query.data}
                onClick={() => {
                  const to = form.getValues("test_to")?.trim();
                  if (!to) {
                    toast.error("Enter a recipient first");
                    return;
                  }
                  test.mutate(to);
                }}
              >
                {test.isPending ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <Send className="size-4" />
                )}
                Send test email
              </Button>
              {!query.data ? (
                <p className="text-xs text-muted-foreground">
                  Save the SMTP settings before testing.
                </p>
              ) : null}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Last test</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              {query.data?.last_tested_at ? (
                <p className="flex items-center gap-1.5 text-emerald-600">
                  <CheckCircle2 className="size-4" />
                  Passed {formatDateTime(query.data.last_tested_at)}
                </p>
              ) : (
                <p className="text-muted-foreground">No successful test yet.</p>
              )}
              {query.data?.last_test_error ? (
                <p className="flex items-start gap-1.5 rounded-lg bg-destructive/10 p-2 text-xs text-destructive">
                  <ShieldAlert className="mt-0.5 size-3.5 shrink-0" />
                  {query.data.last_test_error}
                </p>
              ) : null}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
