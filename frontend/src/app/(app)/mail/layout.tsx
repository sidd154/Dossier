import { AreaTabs } from "@/components/area-tabs";

export default function MailLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div>
      <AreaTabs
        tabs={[
          { href: "/mail/templates", label: "Templates" },
          { href: "/mail/settings", label: "SMTP settings" },
          { href: "/mail/executions", label: "Executions" },
        ]}
      />
      {children}
    </div>
  );
}
