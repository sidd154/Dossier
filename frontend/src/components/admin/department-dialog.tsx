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
import type { Department } from "@/lib/types";

const schema = z.object({
  name: z.string().min(1, "Enter a name").max(200, "Name is too long"),
  description: z.string().max(2000, "Description is too long").optional(),
  is_active: z.boolean(),
});

export type DepartmentValues = z.infer<typeof schema>;

export function DepartmentDialog({
  open,
  onOpenChange,
  department,
  pending,
  onSubmit,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  department: Department | null;
  pending: boolean;
  onSubmit: (values: DepartmentValues) => void;
}) {
  const form = useForm<DepartmentValues>({
    resolver: zodResolver(schema),
    defaultValues: { name: "", description: "", is_active: true },
  });

  useEffect(() => {
    if (!open) return;
    form.reset({
      name: department?.name ?? "",
      description: department?.description ?? "",
      is_active: department?.is_active ?? true,
    });
  }, [open, department, form]);

  const errorFor = (field: keyof DepartmentValues) =>
    form.formState.errors[field]?.message;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>
            {department ? "Edit department" : "New department"}
          </DialogTitle>
          <DialogDescription>
            A department owns its members, source access, and scheduled emails.
          </DialogDescription>
        </DialogHeader>

        <form
          className="space-y-4"
          onSubmit={form.handleSubmit(onSubmit)}
          noValidate
        >
          <div className="space-y-2">
            <Label htmlFor="department-name">Name</Label>
            <Input id="department-name" {...form.register("name")} />
            {errorFor("name") ? (
              <p className="text-xs text-destructive">{errorFor("name")}</p>
            ) : null}
          </div>
          <div className="space-y-2">
            <Label htmlFor="department-description">Description</Label>
            <Textarea
              id="department-description"
              rows={3}
              placeholder="Optional"
              {...form.register("description")}
            />
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
              {department ? "Save changes" : "Create department"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
