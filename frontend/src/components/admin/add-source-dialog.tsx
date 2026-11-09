"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertCircle, Database, Loader2, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";

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
import { Skeleton } from "@/components/ui/skeleton";
import { ApiRequestError, api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { Connector, ConnectorAsset } from "@/lib/types";

export interface NewDataSourcePayload {
  connector_id: string;
  external_id: string;
  name: string;
}

export function AddSourceDialog({
  open,
  onOpenChange,
  connectors,
  pending,
  onSubmit,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  connectors: Connector[];
  pending: boolean;
  onSubmit: (payload: NewDataSourcePayload) => void;
}) {
  const [connectorId, setConnectorId] = useState("");
  const [externalId, setExternalId] = useState("");
  const [name, setName] = useState("");

  useEffect(() => {
    if (!open) return;
    setConnectorId("");
    setExternalId("");
    setName("");
  }, [open]);

  const assets = useQuery({
    queryKey: ["connector-assets", connectorId],
    queryFn: () =>
      api.get<ConnectorAsset[]>(
        `/api/v1/admin/connectors/${connectorId}/assets`,
      ),
    enabled: Boolean(connectorId),
    retry: false,
  });

  useEffect(() => {
    if (!externalId && assets.data?.length) {
      setExternalId(assets.data[0].external_id);
    }
  }, [assets.data, externalId]);

  const selected = assets.data?.find(
    (asset) => asset.external_id === externalId,
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Add a data source</DialogTitle>
          <DialogDescription>
            Pick a connector, then one of the sources it exposes. Permissions
            are granted afterwards, per department.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-2">
            <Label>Connector</Label>
            <Select value={connectorId} onValueChange={setConnectorId}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Choose a connector" />
              </SelectTrigger>
              <SelectContent>
                {connectors.map((connector) => (
                  <SelectItem key={connector.id} value={connector.id}>
                    {connector.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {!connectors.length ? (
              <p className="text-xs text-muted-foreground">
                Create an active connector with credentials first.
              </p>
            ) : null}
          </div>

          {connectorId ? (
            <div className="space-y-2">
              <Label>Source</Label>
              {assets.isLoading ? (
                <div className="space-y-2">
                  <Skeleton className="h-9 w-full" />
                  <Skeleton className="h-9 w-full" />
                </div>
              ) : assets.isError ? (
                <div className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-xs text-destructive">
                  <AlertCircle className="mt-0.5 size-4 shrink-0" />
                  <div className="flex-1">
                    <p>
                      {assets.error instanceof ApiRequestError
                        ? assets.error.message
                        : "Could not list sources from this connector."}
                    </p>
                    <Button
                      type="button"
                      variant="link"
                      size="sm"
                      className="h-auto px-0 text-xs"
                      onClick={() => void assets.refetch()}
                    >
                      <RefreshCw className="size-3" />
                      Try again
                    </Button>
                  </div>
                </div>
              ) : assets.data?.length ? (
                <div className="grid max-h-56 gap-1.5 overflow-y-auto rounded-lg border p-1.5">
                  {assets.data.map((asset) => (
                    <button
                      key={asset.external_id}
                      type="button"
                      onClick={() => setExternalId(asset.external_id)}
                      className={cn(
                        "flex items-center gap-2 rounded-md px-3 py-2 text-left text-sm transition-colors",
                        externalId === asset.external_id
                          ? "bg-accent text-accent-foreground"
                          : "hover:bg-muted",
                      )}
                    >
                      <Database className="size-4 shrink-0" />
                      <span className="min-w-0 flex-1 truncate">
                        {asset.name}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {asset.kind}
                      </span>
                    </button>
                  ))}
                </div>
              ) : (
                <p className="rounded-lg border border-dashed p-4 text-center text-xs text-muted-foreground">
                  This connector exposes no sources.
                </p>
              )}
            </div>
          ) : null}

          <div className="space-y-2">
            <Label htmlFor="source-name">Display name</Label>
            <Input
              id="source-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder={selected?.name ?? "Optional"}
            />
          </div>
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
            disabled={!connectorId || !externalId || pending}
            onClick={() =>
              onSubmit({
                connector_id: connectorId,
                external_id: externalId,
                name: name.trim() || selected?.name || externalId,
              })
            }
          >
            {pending ? <Loader2 className="size-4 animate-spin" /> : null}
            Add source
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
