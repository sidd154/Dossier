"use client";

import { Loader2, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

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
import type {
  Department,
  DepartmentSourceEntry,
  MailFrequency,
  MailSchedule,
  MailTemplate,
} from "@/lib/types";

export interface MailScheduleValues {
  name: string;
  template_id: string;
  enabled: boolean;
  frequency: MailFrequency;
  time_of_day: string;
  weekday: number | null;
  day_of_month: number | null;
  timezone: string;
  row_limit: number;
  source_ids: string[];
}

const TIMEZONES = [
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

const WEEKDAYS = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
];

export function MailScheduleDialog({
  open,
  onOpenChange,
  schedule,
  department,
  templates,
  sources,
  defaultTimezone,
  pending,
  onSubmit,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  schedule: MailSchedule | null;
  department: Department | null;
  templates: MailTemplate[];
  sources: DepartmentSourceEntry[];
  defaultTimezone: string;
  pending: boolean;
  onSubmit: (values: MailScheduleValues) => void;
}) {
  const available = sources.filter(
    (source) => source.granted && source.is_active,
  );

  const [name, setName] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [enabled, setEnabled] = useState(true);
  const [frequency, setFrequency] = useState<MailFrequency>("DAILY");
  const [timeOfDay, setTimeOfDay] = useState("09:00");
  const [weekday, setWeekday] = useState(0);
  const [dayOfMonth, setDayOfMonth] = useState(1);
  const [timezone, setTimezone] = useState("UTC");
  const [rowLimit, setRowLimit] = useState(50);
  const [sourceIds, setSourceIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!open) return;
    setName(schedule?.name ?? "");
    setTemplateId(schedule?.template_id ?? templates[0]?.id ?? "");
    setEnabled(schedule?.enabled ?? true);
    setFrequency(schedule?.frequency ?? "DAILY");
    setTimeOfDay((schedule?.time_of_day ?? "09:00:00").slice(0, 5));
    setWeekday(schedule?.weekday ?? 0);
    setDayOfMonth(schedule?.day_of_month ?? 1);
    setTimezone(schedule?.timezone ?? defaultTimezone ?? "UTC");
    setRowLimit(schedule?.row_limit ?? 50);
    setSourceIds(
      new Set(
        schedule
          ? schedule.source_ids
          : available.map((source) => source.data_source_id),
      ),
    );
    // Initialise from the props present when the dialog opens. The parent only
    // enables the trigger once templates and sources have loaded.
  }, [open]);

  const toggle = (id: string) => {
    setSourceIds((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const submit = () => {
    if (!name.trim()) return toast.error("Give the email a name");
    if (!templateId) return toast.error("Choose a template");
    if (!sourceIds.size) return toast.error("Select at least one source");
    if (frequency === "MONTHLY" && (dayOfMonth < 1 || dayOfMonth > 31)) {
      return toast.error("Day of month must be between 1 and 31");
    }

    onSubmit({
      name: name.trim(),
      template_id: templateId,
      enabled,
      frequency,
      time_of_day: timeOfDay.length === 5 ? `${timeOfDay}:00` : timeOfDay,
      weekday: frequency === "WEEKLY" ? weekday : null,
      day_of_month: frequency === "MONTHLY" ? dayOfMonth : null,
      timezone: timezone.trim() || "UTC",
      row_limit: rowLimit,
      source_ids: Array.from(sourceIds),
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>
            {schedule ? "Edit email" : "New email for"} {department?.name}
          </DialogTitle>
          <DialogDescription>
            Recipients are this department&apos;s active members. Only the
            granted sources you tick here can appear in the generated email.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="email-name">Name</Label>
              <Input
                id="email-name"
                placeholder="Weekly pipeline brief"
                value={name}
                onChange={(event) => setName(event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>Template</Label>
              <Select value={templateId} onValueChange={setTemplateId}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Choose a template" />
                </SelectTrigger>
                <SelectContent>
                  {templates.map((template) => (
                    <SelectItem key={template.id} value={template.id}>
                      {template.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            <div className="space-y-2">
              <Label>Frequency</Label>
              <Select
                value={frequency}
                onValueChange={(value) => setFrequency(value as MailFrequency)}
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="DAILY">Daily</SelectItem>
                  <SelectItem value="WEEKLY">Weekly</SelectItem>
                  <SelectItem value="MONTHLY">Monthly</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {frequency === "WEEKLY" ? (
              <div className="space-y-2">
                <Label>Weekday</Label>
                <Select
                  value={String(weekday)}
                  onValueChange={(value) => setWeekday(Number(value))}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {WEEKDAYS.map((label, index) => (
                      <SelectItem key={label} value={String(index)}>
                        {label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            ) : null}

            {frequency === "MONTHLY" ? (
              <div className="space-y-2">
                <Label htmlFor="day-of-month">Day of month</Label>
                <Input
                  id="day-of-month"
                  type="number"
                  min={1}
                  max={31}
                  value={dayOfMonth}
                  onChange={(event) =>
                    setDayOfMonth(Number(event.target.value))
                  }
                />
              </div>
            ) : null}

            <div className="space-y-2">
              <Label htmlFor="time-of-day">Time</Label>
              <Input
                id="time-of-day"
                type="time"
                value={timeOfDay}
                onChange={(event) => setTimeOfDay(event.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="timezone">Timezone</Label>
              <Input
                id="timezone"
                list="email-timezones"
                value={timezone}
                onChange={(event) => setTimezone(event.target.value)}
              />
              <datalist id="email-timezones">
                {TIMEZONES.map((zone) => (
                  <option key={zone} value={zone} />
                ))}
              </datalist>
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label>Sources</Label>
              <div className="flex gap-2 text-xs">
                <button
                  type="button"
                  className="text-muted-foreground hover:text-foreground"
                  onClick={() =>
                    setSourceIds(
                      new Set(available.map((source) => source.data_source_id)),
                    )
                  }
                >
                  Select all
                </button>
                <button
                  type="button"
                  className="text-muted-foreground hover:text-foreground"
                  onClick={() => setSourceIds(new Set())}
                >
                  Clear
                </button>
              </div>
            </div>
            {available.length ? (
              <div className="max-h-44 space-y-0.5 overflow-y-auto rounded-lg border p-1.5">
                {available.map((source) => (
                  <label
                    key={source.data_source_id}
                    className="flex cursor-pointer items-center gap-2.5 rounded-md px-2 py-1.5 text-sm hover:bg-muted/60"
                  >
                    <input
                      type="checkbox"
                      className="size-4 rounded border-input accent-primary"
                      checked={sourceIds.has(source.data_source_id)}
                      onChange={() => toggle(source.data_source_id)}
                    />
                    <span className="min-w-0 flex-1 truncate">
                      {source.name}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {source.connector_name}
                    </span>
                  </label>
                ))}
              </div>
            ) : (
              <p className="rounded-lg border border-dashed p-3 text-xs text-muted-foreground">
                This department has no granted sources yet.{" "}
                <a
                  className="underline"
                  href={`/departments/${department?.id}/sources`}
                >
                  Grant access first
                </a>
                .
              </p>
            )}
            <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <ShieldCheck className="size-3.5" />
              Only granted, active sources are listed.
            </p>
          </div>

          <details className="rounded-lg border p-3">
            <summary className="cursor-pointer text-sm font-medium">
              Advanced
            </summary>
            <div className="mt-3 grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="row-limit">Sample rows per source</Label>
                <Input
                  id="row-limit"
                  type="number"
                  min={1}
                  max={500}
                  value={rowLimit}
                  onChange={(event) => setRowLimit(Number(event.target.value))}
                />
                <p className="text-xs text-muted-foreground">
                  More rows give the model more context but cost more tokens.
                </p>
              </div>
              <label className="flex items-center gap-2.5 self-end pb-2 text-sm">
                <input
                  type="checkbox"
                  className="size-4 rounded border-input accent-primary"
                  checked={enabled}
                  onChange={(event) => setEnabled(event.target.checked)}
                />
                Enabled
              </label>
            </div>
          </details>
        </div>

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
          >
            Cancel
          </Button>
          <Button
            type="button"
            onClick={submit}
            disabled={pending || !department}
          >
            {pending ? <Loader2 className="size-4 animate-spin" /> : null}
            {schedule ? "Save changes" : "Create email"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
