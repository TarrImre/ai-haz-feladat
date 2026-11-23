import type { ReactNode } from "react";

export default function Badge({ kind, children }: { kind: string; children: ReactNode }) {
  return <span className={`badge b-${kind}`}>{children}</span>;
}
