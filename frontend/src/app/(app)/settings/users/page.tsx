"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ChevronLeft,
  ChevronRight,
  KeyRound,
  MoreHorizontal,
  Search,
  UserPlus,
  Users,
} from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { DepartmentSelect } from "@/components/admin/department-select";
import { TempPasswordDialog } from "@/components/admin/temp-password-dialog";
import {
  UserDialog,
  type UserFormValues,
} from "@/components/admin/user-dialog";
import { PageHeader } from "@/components/page-header";
import { EmptyState, ErrorState } from "@/components/states";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { ApiRequestError, api, queryString } from "@/lib/api";
import { formatRelative, initials } from "@/lib/format";
import type {
  CreatedUser,
  Department,
  Page,
  PasswordResetResponse,
  User,
} from "@/lib/types";

const PAGE_SIZE = 10;

export default function UsersPage() {
  const queryClient = useQueryClient();

  const [search, setSearch] = useState("");
  const debouncedSearch = useDebouncedValue(search);
  const [role, setRole] = useState("ALL");
  const [status, setStatus] = useState("ALL");
  const [departmentId, setDepartmentId] = useState("ALL");
  const [page, setPage] = useState(1);

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<User | null>(null);
  const [tempPassword, setTempPassword] = useState<{
    email: string;
    password: string;
  } | null>(null);
  const [disabling, setDisabling] = useState<User | null>(null);

  useEffect(() => {
    const initial = new URLSearchParams(window.location.search).get(
      "department_id",
    );
    if (initial) setDepartmentId(initial);
  }, []);

  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, role, status, departmentId]);

  const params = {
    q: debouncedSearch,
    role: role === "ALL" ? undefined : role,
    status: status === "ALL" ? undefined : status,
    department_id: departmentId === "ALL" ? undefined : departmentId,
    page,
    page_size: PAGE_SIZE,
  };

  const usersQuery = useQuery({
    queryKey: ["users", params],
    queryFn: () =>
      api.get<Page<User>>(`/api/v1/admin/users${queryString(params)}`),
  });

  const departmentsQuery = useQuery({
    queryKey: ["departments", "picker"],
    queryFn: () =>
      api.get<Page<Department>>(
        "/api/v1/admin/departments?page=1&page_size=100",
      ),
  });
  const departments = departmentsQuery.data?.items ?? [];

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["users"] });
    void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    void queryClient.invalidateQueries({ queryKey: ["audit"] });
  };

  const createMutation = useMutation({
    mutationFn: (values: UserFormValues) =>
      api.post<CreatedUser>("/api/v1/admin/users", {
        email: values.email,
        full_name: values.full_name,
        department_id: values.department_id,
        role: values.role,
      }),
    onSuccess: (created) => {
      setFormOpen(false);
      setTempPassword({
        email: created.email,
        password: created.temporary_password,
      });
      refresh();
    },
    onError: (error) => toast.error(errorMessage(error)),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, values }: { id: string; values: UserFormValues }) =>
      api.patch<User>(`/api/v1/admin/users/${id}`, {
        full_name: values.full_name,
        department_id: values.department_id,
        role: values.role,
        status: values.status,
      }),
    onSuccess: () => {
      setFormOpen(false);
      toast.success("User updated");
      refresh();
    },
    onError: (error) => toast.error(errorMessage(error)),
  });

  const resetMutation = useMutation({
    mutationFn: (user: User) =>
      api.post<PasswordResetResponse>(
        `/api/v1/admin/users/${user.id}/reset-password`,
      ),
    onSuccess: (result, user) => {
      setTempPassword({
        email: user.email,
        password: result.temporary_password,
      });
      refresh();
    },
    onError: (error) => toast.error(errorMessage(error)),
  });

  const statusMutation = useMutation({
    mutationFn: ({ user, next }: { user: User; next: "ACTIVE" | "DISABLED" }) =>
      api.patch<User>(`/api/v1/admin/users/${user.id}`, { status: next }),
    onMutate: async ({ user, next }) => {
      await queryClient.cancelQueries({ queryKey: ["users"] });
      const previous = queryClient.getQueriesData<Page<User>>({
        queryKey: ["users"],
      });
      queryClient.setQueriesData<Page<User>>({ queryKey: ["users"] }, (old) =>
        old
          ? {
              ...old,
              items: old.items.map((item) =>
                item.id === user.id ? { ...item, status: next } : item,
              ),
            }
          : old,
      );
      return { previous };
    },
    onError: (error, _variables, context) => {
      context?.previous.forEach(([key, data]) => {
        queryClient.setQueryData(key, data);
      });
      toast.error(errorMessage(error));
    },
    onSuccess: (_data, variables) => {
      toast.success(
        variables.next === "DISABLED" ? "User disabled" : "User enabled",
      );
      refresh();
    },
  });

  const submitForm = (values: UserFormValues) => {
    if (editing) {
      updateMutation.mutate({ id: editing.id, values });
    } else {
      createMutation.mutate(values);
    }
  };

  const total = usersQuery.data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const first = total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
  const last = Math.min(page * PAGE_SIZE, total);

  return (
    <div>
      <PageHeader
        title="Users"
        description="Accounts are created here. Members never self-register."
        actions={
          <Button
            onClick={() => {
              setEditing(null);
              setFormOpen(true);
            }}
          >
            <UserPlus className="size-4" />
            Add user
          </Button>
        }
      />

      <Card className="mb-4">
        <CardContent className="flex flex-col gap-3 p-4 lg:flex-row lg:items-center">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              className="pl-9"
              placeholder="Search by name or email"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
          <div className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap">
            <Select value={role} onValueChange={setRole}>
              <SelectTrigger className="w-full sm:w-36">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="ALL">All roles</SelectItem>
                <SelectItem value="ADMIN">Administrator</SelectItem>
                <SelectItem value="USER">Member</SelectItem>
              </SelectContent>
            </Select>
            <Select value={status} onValueChange={setStatus}>
              <SelectTrigger className="w-full sm:w-36">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="ALL">All statuses</SelectItem>
                <SelectItem value="ACTIVE">Active</SelectItem>
                <SelectItem value="DISABLED">Disabled</SelectItem>
              </SelectContent>
            </Select>
            <div className="col-span-2 min-w-44 sm:col-span-1">
              <DepartmentSelect
                value={departmentId}
                onValueChange={setDepartmentId}
                departments={departments}
                allowAll
                placeholder="All departments"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          {usersQuery.isError ? (
            <ErrorState
              message={errorMessage(usersQuery.error)}
              onRetry={() => void usersQuery.refetch()}
            />
          ) : usersQuery.isLoading ? (
            <TableSkeleton />
          ) : usersQuery.data && usersQuery.data.items.length > 0 ? (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>User</TableHead>
                    <TableHead>Department</TableHead>
                    <TableHead>Role</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Last sign-in</TableHead>
                    <TableHead className="w-10" />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {usersQuery.data.items.map((user) => (
                    <TableRow key={user.id}>
                      <TableCell>
                        <div className="flex items-center gap-3">
                          <Avatar className="size-8">
                            <AvatarFallback className="text-xs font-semibold">
                              {initials(user.full_name)}
                            </AvatarFallback>
                          </Avatar>
                          <div className="min-w-0">
                            <p className="truncate text-sm font-medium">
                              {user.full_name}
                            </p>
                            <p className="truncate text-xs text-muted-foreground">
                              {user.email}
                            </p>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell className="text-sm">
                        {user.department?.name ?? "—"}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={
                            user.role === "ADMIN" ? "default" : "secondary"
                          }
                        >
                          {user.role === "ADMIN" ? "Admin" : "Member"}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <StatusBadge status={user.status} />
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {formatRelative(user.last_login_at)}
                      </TableCell>
                      <TableCell className="text-right">
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button
                              variant="ghost"
                              size="icon"
                              aria-label={`Actions for ${user.full_name}`}
                            >
                              <MoreHorizontal className="size-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end" className="w-48">
                            <DropdownMenuItem
                              onSelect={() => {
                                setEditing(user);
                                setFormOpen(true);
                              }}
                            >
                              Edit user
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onSelect={() => resetMutation.mutate(user)}
                            >
                              <KeyRound className="size-4" />
                              Reset password
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            {user.status === "ACTIVE" ? (
                              <DropdownMenuItem
                                variant="destructive"
                                onSelect={() => setDisabling(user)}
                              >
                                Disable account
                              </DropdownMenuItem>
                            ) : (
                              <DropdownMenuItem
                                onSelect={() =>
                                  statusMutation.mutate({
                                    user,
                                    next: "ACTIVE",
                                  })
                                }
                              >
                                Enable account
                              </DropdownMenuItem>
                            )}
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              <div className="flex items-center justify-between gap-3 border-t px-4 py-3">
                <p className="text-xs text-muted-foreground">
                  {first}–{last} of {total}
                </p>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page <= 1}
                    onClick={() =>
                      setPage((current) => Math.max(1, current - 1))
                    }
                  >
                    <ChevronLeft className="size-4" />
                    Previous
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page >= pageCount}
                    onClick={() =>
                      setPage((current) => Math.min(pageCount, current + 1))
                    }
                  >
                    Next
                    <ChevronRight className="size-4" />
                  </Button>
                </div>
              </div>
            </>
          ) : (
            <EmptyState
              icon={Users}
              title={
                debouncedSearch ||
                role !== "ALL" ||
                status !== "ALL" ||
                departmentId !== "ALL"
                  ? "No users match these filters"
                  : "No users yet"
              }
              description={
                debouncedSearch ||
                role !== "ALL" ||
                status !== "ALL" ||
                departmentId !== "ALL"
                  ? "Try clearing the search or filters."
                  : "Add your first team member to get started."
              }
              action={
                <Button
                  variant="outline"
                  onClick={() => {
                    setEditing(null);
                    setFormOpen(true);
                  }}
                >
                  <UserPlus className="size-4" />
                  Add user
                </Button>
              }
            />
          )}
        </CardContent>
      </Card>

      <UserDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        mode={editing ? "edit" : "create"}
        user={editing}
        departments={departments}
        defaultDepartmentId={
          departmentId === "ALL" ? undefined : departmentId
        }
        pending={createMutation.isPending || updateMutation.isPending}
        onSubmit={submitForm}
      />

      <TempPasswordDialog
        open={Boolean(tempPassword)}
        onOpenChange={(open) => {
          if (!open) setTempPassword(null);
        }}
        email={tempPassword?.email ?? ""}
        password={tempPassword?.password ?? null}
      />

      <AlertDialog
        open={Boolean(disabling)}
        onOpenChange={(open) => {
          if (!open) setDisabling(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Disable this account?</AlertDialogTitle>
            <AlertDialogDescription>
              {disabling?.full_name} will be signed out immediately and will not
              be able to sign in until the account is enabled again.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (disabling) {
                  statusMutation.mutate({ user: disabling, next: "DISABLED" });
                }
                setDisabling(null);
              }}
            >
              Disable account
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function StatusBadge({ status }: { status: User["status"] }) {
  return (
    <Badge variant={status === "ACTIVE" ? "outline" : "secondary"}>
      <span
        className={
          status === "ACTIVE"
            ? "mr-1.5 size-1.5 rounded-full bg-emerald-500"
            : "mr-1.5 size-1.5 rounded-full bg-muted-foreground"
        }
      />
      {status === "ACTIVE" ? "Active" : "Disabled"}
    </Badge>
  );
}

function TableSkeleton() {
  return (
    <div className="divide-y">
      {Array.from({ length: 6 }).map((_, index) => (
        <div key={index} className="flex items-center gap-4 px-4 py-4">
          <Skeleton className="size-8 rounded-full" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-3.5 w-40" />
            <Skeleton className="h-3 w-56" />
          </div>
          <Skeleton className="h-5 w-16" />
          <Skeleton className="hidden h-5 w-20 sm:block" />
        </div>
      ))}
    </div>
  );
}

function errorMessage(error: unknown): string {
  return error instanceof ApiRequestError
    ? error.message
    : "Something went wrong. Try again.";
}
