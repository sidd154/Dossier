"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, Loader2, Sparkles } from "lucide-react";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { PageHeader } from "@/components/page-header";
import { ErrorState } from "@/components/states";
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
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { ApiRequestError, api } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { Organisation } from "@/lib/types";

const schema = z.object({
  name: z.string().min(1, "Enter the organisation name").max(200),
  description: z.string().max(4000, "Description is too long").optional(),
  industry: z.string().max(120, "Industry is too long").optional(),
  timezone: z.string().min(1, "Enter a timezone"),
  locations: z.string().optional(),
});

type Values = z.infer<typeof schema>;

const COMMON_TIMEZONES = [
  "UTC",
  "Europe/London",
  "Europe/Dublin",
  "Europe/Paris",
  "Europe/Berlin",
  "Asia/Kolkata",
  "Asia/Dubai",
  "Asia/Singapore",
  "America/New_York",
  "America/Chicago",
  "America/Los_Angeles",
  "Australia/Sydney",
];

export default function OrganisationPage() {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["organisation"],
    queryFn: () => api.get<Organisation>("/api/v1/admin/organisation"),
  });

  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: "",
      description: "",
      industry: "",
      timezone: "UTC",
      locations: "",
    },
  });

  useEffect(() => {
    if (!query.data) return;
    form.reset({
      name: query.data.name,
      description: query.data.description ?? "",
      industry: query.data.industry ?? "",
      timezone: query.data.timezone,
      locations: query.data.locations.join(", "),
    });
  }, [query.data, form]);

  const mutation = useMutation({
    mutationFn: (values: Values) =>
      api.patch<Organisation>("/api/v1/admin/organisation", {
        name: values.name,
        description: values.description?.trim() ? values.description : null,
        industry: values.industry?.trim() ? values.industry : null,
        timezone: values.timezone,
        locations: (values.locations ?? "")
          .split(",")
          .map((location) => location.trim())
          .filter(Boolean),
      }),
    onSuccess: (organisation) => {
      queryClient.setQueryData(["organisation"], organisation);
      void queryClient.invalidateQueries({ queryKey: ["audit"] });
      toast.success("Organisation settings saved");
    },
    onError: (error) => {
      toast.error(
        error instanceof ApiRequestError
          ? error.message
          : "Could not save the organisation settings.",
      );
    },
  });

  const errorFor = (field: keyof Values) =>
    form.formState.errors[field]?.message;

  return (
    <div>
      <PageHeader
        title="Organisation"
        description="This context is included in every mail generation prompt."
      />

      {query.isError ? (
        <Card>
          <ErrorState
            message={
              query.error instanceof ApiRequestError
                ? query.error.message
                : "Could not load organisation settings."
            }
            onRetry={() => void query.refetch()}
          />
        </Card>
      ) : (
        <div className="grid gap-4 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Building2 className="size-4 text-muted-foreground" />
                Profile
              </CardTitle>
              <CardDescription>
                A clear description improves the quality of grounded answers.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {query.isLoading ? (
                <div className="space-y-4">
                  {Array.from({ length: 5 }).map((_, index) => (
                    <div key={index} className="space-y-2">
                      <Skeleton className="h-3.5 w-24" />
                      <Skeleton className="h-9 w-full" />
                    </div>
                  ))}
                </div>
              ) : (
                <form
                  className="space-y-5"
                  onSubmit={form.handleSubmit((values) =>
                    mutation.mutate(values),
                  )}
                  noValidate
                >
                  <div className="space-y-2">
                    <Label htmlFor="name">Organisation name</Label>
                    <Input
                      id="name"
                      aria-invalid={Boolean(errorFor("name"))}
                      {...form.register("name")}
                    />
                    {errorFor("name") ? (
                      <p className="text-xs text-destructive">
                        {errorFor("name")}
                      </p>
                    ) : null}
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="description">Description</Label>
                    <Textarea
                      id="description"
                      rows={5}
                      placeholder="What the organisation does, who it serves, and anything the assistant should always know."
                      {...form.register("description")}
                    />
                    {errorFor("description") ? (
                      <p className="text-xs text-destructive">
                        {errorFor("description")}
                      </p>
                    ) : null}
                  </div>

                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="space-y-2">
                      <Label htmlFor="industry">Industry</Label>
                      <Input
                        id="industry"
                        placeholder="e.g. Professional services"
                        {...form.register("industry")}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="timezone">Timezone</Label>
                      <Input
                        id="timezone"
                        list="timezones"
                        aria-invalid={Boolean(errorFor("timezone"))}
                        {...form.register("timezone")}
                      />
                      <datalist id="timezones">
                        {COMMON_TIMEZONES.map((zone) => (
                          <option key={zone} value={zone} />
                        ))}
                      </datalist>
                      {errorFor("timezone") ? (
                        <p className="text-xs text-destructive">
                          {errorFor("timezone")}
                        </p>
                      ) : null}
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="locations">Locations</Label>
                    <Input
                      id="locations"
                      placeholder="London, Lisbon, Singapore"
                      {...form.register("locations")}
                    />
                    <p className="text-xs text-muted-foreground">
                      Separate locations with commas.
                    </p>
                  </div>

                  <div className="flex items-center justify-between gap-3 border-t pt-4">
                    <p className="text-xs text-muted-foreground">
                      {query.data
                        ? `Last updated ${formatDateTime(query.data.updated_at)}`
                        : null}
                    </p>
                    <Button
                      type="submit"
                      disabled={mutation.isPending || !form.formState.isDirty}
                    >
                      {mutation.isPending ? (
                        <Loader2 className="size-4 animate-spin" />
                      ) : null}
                      Save changes
                    </Button>
                  </div>
                </form>
              )}
            </CardContent>
          </Card>

          <Card className="h-fit">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Sparkles className="size-4 text-muted-foreground" />
                Why this matters
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm text-muted-foreground">
              <p>
                The organisation profile is included in every mail generation prompt
                as context. It is never used to widen data access.
              </p>
              <p>
                Mail templates can reference the organisation name and other
                profile fields as variables.
              </p>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
