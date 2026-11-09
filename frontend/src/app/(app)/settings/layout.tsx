import { AreaTabs } from "@/components/area-tabs";

export default function SettingsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div>
      <AreaTabs
        tabs={[
          { href: "/settings/organisation", label: "Organisation" },
          { href: "/settings/users", label: "Users" },
          { href: "/settings/audit", label: "Audit log" },
        ]}
      />
      {children}
    </div>
  );
}
