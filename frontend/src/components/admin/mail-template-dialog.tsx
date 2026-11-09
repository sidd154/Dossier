"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";
import { useEffect } from "react";
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
import { Textarea } from "@/components/ui/textarea";
import type { MailTemplate } from "@/lib/types";

const schema = z.object({
  name: z.string().min(1, "Enter a name").max(200),
  description: z.string().max(2000).optional(),
  subject_template: z.string().min(1, "Enter a subject").max(500),
  system_prompt: z.string().min(1, "Enter the prompt").max(8000),
  is_active: z.boolean(),
});

export type MailTemplateValues = z.infer<typeof schema>;

export function MailTemplateDialog({
  open,
  onOpenChange,
  template,
  pending,
  onSubmit,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  template: MailTemplate | null;
  pending: boolean;
  onSubmit: (values: MailTemplateValues) => void;
}) {
  const form = useForm<MailTemplateValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: "",
      description: "",
      subject_template: "",
      system_prompt: "",
      is_active: true,
    },
  });

  useEffect(() => {
    if (!open) return;
    form.reset({
      name: template?.name ?? "",
      description: template?.description ?? "",
      subject_template:
        template?.subject_template ?? "{{ department.name }} update",
      system_prompt: template?.system_prompt ?? "",
      is_active: template?.is_active ?? true,
    });
  }, [open, template, form]);

  const errorFor = (field: keyof MailTemplateValues) =>
    form.formState.errors[field]?.message;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[88vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>
            {template ? "Edit template" : "New template"}
          </DialogTitle>
          <DialogDescription>
            The prompt is the system instruction. The email body is generated
            from it using only the data each recipient&apos;s department may
            access.
          </DialogDescription>
        </DialogHeader>

        <form
          className="space-y-4"
          onSubmit={form.handleSubmit(onSubmit)}
          noValidate
        >
          <div className="space-y-2">
            <Label htmlFor="template-name">Name</Label>
            <Input id="template-name" {...form.register("name")} />
            {errorFor("name") ? (
              <p className="text-xs text-destructive">{errorFor("name")}</p>
            ) : null}
          </div>

          <div className="space-y-2">
            <Label htmlFor="template-description">Description</Label>
            <Input
              id="template-description"
              placeholder="Optional"
              {...form.register("description")}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="subject_template">Subject template</Label>
            <Input
              id="subject_template"
              placeholder="{{ organisation.name }} — {{ date }}"
              {...form.register("subject_template")}
            />
            <p className="text-xs text-muted-foreground">
              Jinja2. Available: <code>organisation.name</code>,{" "}
              <code>department.name</code>, <code>date</code>,{" "}
              <code>user.full_name</code>, <code>user.email</code>.
            </p>
            {errorFor("subject_template") ? (
              <p className="text-xs text-destructive">
                {errorFor("subject_template")}
              </p>
            ) : null}
          </div>

          <div className="space-y-2">
            <Label htmlFor="system_prompt">System prompt</Label>
            <Textarea
              id="system_prompt"
              rows={10}
              placeholder={
                "Write a short daily brief for this department. Lead with the most important number, then three bullets of context. Do not speculate."
              }
              {...form.register("system_prompt")}
            />
            <p className="text-xs text-muted-foreground">
              Write the instruction only. Greetings, signatures, and safety
              rules are added automatically.
            </p>
            {errorFor("system_prompt") ? (
              <p className="text-xs text-destructive">
                {errorFor("system_prompt")}
              </p>
            ) : null}
          </div>

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
              {template ? "Save changes" : "Create template"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
