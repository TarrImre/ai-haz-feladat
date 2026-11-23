import Dashboard from "@/components/Dashboard";
import { DEFAULT_QUERY, networkInvoices } from "@/network/network.invoices";

export const dynamic = "force-dynamic";

export default async function Page() {
  const [report, invoices] = await Promise.all([
    networkInvoices.report().then((res) => res.data).catch(() => null),
    networkInvoices.list(DEFAULT_QUERY).then((res) => res.data).catch(() => null),
  ]);
  return <Dashboard initial={report} initialInvoices={invoices} />;
}
