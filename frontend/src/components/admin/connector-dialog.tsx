"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";
import { useEffect, useMemo } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import type { Connector, ConnectorType } from "@/lib/types";

export interface ConnectorPayload {
  name: string;
  type: ConnectorType;
  is_active: boolean;
  config: Record<string, unknown>;
  credentials?: Record<string, string>;
}

const baseSchema = z.object({
  name: z.string().min(1, "Enter a name").max(200),
  type: z.enum(["GOOGLE_SHEETS", "ZOHO_CRM"]),
  is_active: z.boolean(),
  spreadsheet_id: z.string().optional(),
  client_email: z.string().optional(),
  private_key: z.string().optional(),
  api_domain: z.string().optional(),
  client_id: z.string().optional(),
  client_secret: z.string().optional(),
  refresh_token: z.string().optional(),
});

type Values = z.infer<typeof baseSchema>;

export function ConnectorDialog({
  open,
  onOpenChange,
  connector,
  pending,
  onSubmit,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  connector: Connector | null;
  pending: boolean;
  onSubmit: (payload: ConnectorPayload) => void;
}) {
  const editing = Boolean(connector);

  const schema = useMemo(
    () =>
      baseSchema.superRefine((values, ctx) => {
        const require = (field: keyof Values, message: string) => {
          if (!String(values[field] ?? "").trim()) {
            ctx.addIssue({ code: "custom", path: [field], message });
          }
        };

        if (values.type === "GOOGLE_SHEETS") {
          require("spreadsheet_id", "Enter the spreadsheet id");
          require("client_email", "Enter the service account email");
          if (!editing || values.private_key) {
            require("private_key", "Paste the service account private key");
          }
        } else {
          require("api_domain", "Enter the Zoho API domain");
          require("client_id", "Enter the client id");
          if (!editing || values.client_secret) {
            require("client_secret", "Enter the client secret");
          }
          if (!editing || values.refresh_token) {
            require("refresh_token", "Enter the refresh token");
          }
        }
      }),
    [editing],
  );

  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: "",
      type: "GOOGLE_SHEETS",
      is_active: true,
      spreadsheet_id: "",
      client_email: "",
      private_key: "",
      api_domain: "https://www.zohoapis.com",
      client_id: "",
      client_secret: "",
      refresh_token: "",
    },
  });

  useEffect(() => {
    if (!open) return;
    const config = connector?.config ?? {};
    form.reset({
      name: connector?.name ?? "",
      type: connector?.type ?? "GOOGLE_SHEETS",
      is_active: connector?.is_active ?? true,
      spreadsheet_id: String(config.spreadsheet_id ?? ""),
      client_email: "",
      private_key: "",
      api_domain: String(config.api_domain ?? "https://www.zohoapis.com"),
      client_id: "",
      client_secret: "",
      refresh_token: "",
    });
  }, [open, connector, form]);

  const type = form.watch("type");
  const errorFor = (field: keyof Values) =>
    form.formState.errors[field]?.message;

  const submit = (values: Values) => {
    const config: Record<string, unknown> =
      values.type === "GOOGLE_SHEETS"
        ? { spreadsheet_id: values.spreadsheet_id?.trim() }
        : { api_domain: values.api_domain?.trim() };

    const credentials: Record<string, string> = {};
    if (values.type === "GOOGLE_SHEETS") {
      if (values.client_email?.trim())
        credentials.client_email = values.client_email.trim();
      if (values.private_key?.trim())
        credentials.private_key = values.private_key.trim();
    } else {
      if (values.client_id?.trim())
        credentials.client_id = values.client_id.trim();
      if (values.client_secret?.trim())
        credentials.client_secret = values.client_secret.trim();
      if (values.refresh_token?.trim())
        credentials.refresh_token = values.refresh_token.trim();
    }

    onSubmit({
      name: values.name.trim(),
      type: values.type,
      is_active: values.is_active,
      config,
      credentials: Object.keys(credentials).length ? credentials : undefined,
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[88vh] overflow-y-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>
            {editing ? "Edit connector" : "Add a connector"}
          </DialogTitle>
          <DialogDescription>
            Credentials are encrypted at rest and never returned by the API.
          </DialogDescription>
        </DialogHeader>

        <form
          className="space-y-4"
          onSubmit={form.handleSubmit(submit)}
          noValidate
        >
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="name">Name</Label>
              <Input id="name" {...form.register("name")} />
              {errorFor("name") ? (
                <p className="text-xs text-destructive">{errorFor("name")}</p>
              ) : null}
            </div>
            <div className="space-y-2">
              <Label>Type</Label>
              <Select
                value={type}
                disabled={editing}
                onValueChange={(value) =>
                  form.setValue("type", value as ConnectorType)
                }
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="GOOGLE_SHEETS">Google Sheets</SelectItem>
                  <SelectItem value="ZOHO_CRM">Zoho CRM</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {type === "GOOGLE_SHEETS" ? (
            <>
              <div className="space-y-2">
                <Label htmlFor="spreadsheet_id">Spreadsheet id</Label>
                <Input
                  id="spreadsheet_id"
                  placeholder="From the sheet URL, between /d/ and /edit"
                  {...form.register("spreadsheet_id")}
                />
                {errorFor("spreadsheet_id") ? (
                  <p className="text-xs text-destructive">
                    {errorFor("spreadsheet_id")}
                  </p>
                ) : null}
              </div>
              <div className="space-y-2">
                <Label htmlFor="client_email">Service account email</Label>
                <Input id="client_email" {...form.register("client_email")} />
                {errorFor("client_email") ? (
                  <p className="text-xs text-destructive">
                    {errorFor("client_email")}
                  </p>
                ) : null}
                <p className="text-xs text-muted-foreground">
                  Share the spreadsheet with this address as a viewer.
                </p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="private_key">
                  Private key {editing ? "(leave blank to keep)" : ""}
                </Label>
                <Textarea
                  id="private_key"
                  rows={5}
                  className="font-mono text-xs"
                  placeholder="-----BEGIN PRIVATE KEY-----"
                  {...form.register("private_key")}
                />
                {errorFor("private_key") ? (
                  <p className="text-xs text-destructive">
                    {errorFor("private_key")}
                  </p>
                ) : null}
              </div>
            </>
          ) : (
            <>
              <div className="space-y-2">
                <Label htmlFor="api_domain">API domain</Label>
                <Input
                  id="api_domain"
                  placeholder="https://www.zohoapis.com"
                  {...form.register("api_domain")}
                />
                {errorFor("api_domain") ? (
                  <p className="text-xs text-destructive">
                    {errorFor("api_domain")}
                  </p>
                ) : null}
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="client_id">Client id</Label>
                  <Input id="client_id" {...form.register("client_id")} />
                  {errorFor("client_id") ? (
                    <p className="text-xs text-destructive">
                      {errorFor("client_id")}
                    </p>
                  ) : null}
                </div>
                <div className="space-y-2">
                  <Label htmlFor="client_secret">
                    Client secret {editing ? "(leave blank to keep)" : ""}
                  </Label>
                  <Input
                    id="client_secret"
                    type="password"
                    {...form.register("client_secret")}
                  />
                  {errorFor("client_secret") ? (
                    <p className="text-xs text-destructive">
                      {errorFor("client_secret")}
                    </p>
                  ) : null}
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="refresh_token">
                  Refresh token {editing ? "(leave blank to keep)" : ""}
                </Label>
                <Input
                  id="refresh_token"
                  type="password"
                  {...form.register("refresh_token")}
                />
                {errorFor("refresh_token") ? (
                  <p className="text-xs text-destructive">
                    {errorFor("refresh_token")}
                  </p>
                ) : null}
              </div>
            </>
          )}

          <label className="flex items-center gap-2.5 text-sm">
            <input
              type="checkbox"
              className="size-4 rounded border-input accent-primary"
              {...form.register("is_active")}
            />
            Active
          </label>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={pending}>
              {pending ? <Loader2 className="size-4 animate-spin" /> : null}
              {editing ? "Save changes" : "Create connector"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
