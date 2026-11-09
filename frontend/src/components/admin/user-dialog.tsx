"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { DepartmentSelect } from "@/components/admin/department-select";
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
import type { Department, User } from "@/lib/types";

const schema = z.object({
  email: z.email("Enter a valid email address"),
  full_name: z
    .string()
    .min(2, "Enter a full name")
    .max(200, "Name is too long"),
  department_id: z.string().min(1, "Choose a department"),
  role: z.enum(["ADMIN", "USER"]),
  status: z.enum(["ACTIVE", "DISABLED"]),
});

export type UserFormValues = z.infer<typeof schema>;

export function UserDialog({
  open,
  onOpenChange,
  mode,
  user,
  departments,
  defaultDepartmentId,
  pending,
  onSubmit,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mode: "create" | "edit";
  user?: User | null;
  departments: Department[];
  defaultDepartmentId?: string;
  pending: boolean;
  onSubmit: (values: UserFormValues) => void;
}) {
  const form = useForm<UserFormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      email: "",
      full_name: "",
      department_id: "",
      role: "USER",
      status: "ACTIVE",
    },
  });

  useEffect(() => {
    if (!open) return;
    form.reset({
      email: user?.email ?? "",
      full_name: user?.full_name ?? "",
      department_id: user?.department_id ?? defaultDepartmentId ?? "",
      role: user?.role ?? "USER",
      status: user?.status ?? "ACTIVE",
    });
  }, [open, user, defaultDepartmentId, form]);

  const errorFor = (field: keyof UserFormValues) =>
    form.formState.errors[field]?.message;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>
            {mode === "create" ? "Add a user" : "Edit user"}
          </DialogTitle>
          <DialogDescription>
            {mode === "create"
              ? "A temporary password is generated and shown once."
              : "Update the account's name, department, role, or status."}
          </DialogDescription>
        </DialogHeader>

        <form
          className="space-y-4"
          onSubmit={form.handleSubmit(onSubmit)}
          noValidate
        >
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              autoComplete="off"
              disabled={mode === "edit"}
              aria-invalid={Boolean(errorFor("email"))}
              {...form.register("email")}
            />
            {errorFor("email") ? (
              <p className="text-xs text-destructive">{errorFor("email")}</p>
            ) : null}
          </div>

          <div className="space-y-2">
            <Label htmlFor="full_name">Full name</Label>
            <Input
              id="full_name"
              autoComplete="off"
              aria-invalid={Boolean(errorFor("full_name"))}
              {...form.register("full_name")}
            />
            {errorFor("full_name") ? (
              <p className="text-xs text-destructive">
                {errorFor("full_name")}
              </p>
            ) : null}
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>Department</Label>
              <DepartmentSelect
                value={form.watch("department_id")}
                onValueChange={(value) =>
                  form.setValue("department_id", value, {
                    shouldValidate: true,
                  })
                }
                departments={departments}
              />
              {errorFor("department_id") ? (
                <p className="text-xs text-destructive">
                  {errorFor("department_id")}
                </p>
              ) : null}
            </div>

            <div className="space-y-2">
              <Label>Role</Label>
              <Select
                value={form.watch("role")}
                onValueChange={(value) =>
                  form.setValue("role", value as UserFormValues["role"])
                }
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="USER">Member</SelectItem>
                  <SelectItem value="ADMIN">Administrator</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {mode === "edit" ? (
            <div className="space-y-2">
              <Label>Status</Label>
              <Select
                value={form.watch("status")}
                onValueChange={(value) =>
                  form.setValue("status", value as UserFormValues["status"])
                }
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="ACTIVE">Active</SelectItem>
                  <SelectItem value="DISABLED">Disabled</SelectItem>
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                Disabling an account signs the user out immediately.
              </p>
            </div>
          ) : null}

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
              {mode === "create" ? "Create user" : "Save changes"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
