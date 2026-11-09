"use client";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { Department } from "@/lib/types";

export function DepartmentSelect({
  value,
  onValueChange,
  departments,
  placeholder = "Select a department",
  allowAll = false,
  disabled = false,
}: {
  value: string;
  onValueChange: (value: string) => void;
  departments: Department[];
  placeholder?: string;
  allowAll?: boolean;
  disabled?: boolean;
}) {
  return (
    <Select value={value} onValueChange={onValueChange} disabled={disabled}>
      <SelectTrigger className="w-full">
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        {allowAll ? <SelectItem value="ALL">All departments</SelectItem> : null}
        {departments.map((department) => (
          <SelectItem
            key={department.id}
            value={department.id}
            disabled={!department.is_active}
          >
            {department.name}
            {!department.is_active ? " (inactive)" : ""}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
