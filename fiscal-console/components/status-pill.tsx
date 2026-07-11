import type { FiscalStatus } from "@/lib/demo-data";

export function StatusPill({ status, children }: { status: FiscalStatus; children: React.ReactNode }) {
  return <span className={`status status-${status}`}><span className="status-dot" />{children}</span>;
}
