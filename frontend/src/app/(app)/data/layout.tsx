import { AreaTabs } from "@/components/area-tabs";

export default function DataLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div>
      <AreaTabs
        tabs={[
          { href: "/data/connectors", label: "Connectors" },
          { href: "/data/sources", label: "Sources" },
        ]}
      />
      {children}
    </div>
  );
}
