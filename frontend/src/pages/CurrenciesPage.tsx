import LookupCrudPage from "@/components/LookupCrudPage";
import { Currency } from "@/types";

export default function CurrenciesPage() {
  return (
    <LookupCrudPage<Currency>
      title="Currencies"
      description="Currencies available for company base currency and future multi-currency lease pricing."
      endpoint="/currencies"
      permissionModule="currencies"
      columns={[
        { header: "Code", render: (r) => <span className="font-mono text-xs font-semibold">{r.code}</span> },
        { header: "Name", render: (r) => r.name },
        { header: "Symbol", render: (r) => r.symbol },
        { header: "Rate to Base", render: (r) => r.exchange_rate_to_base },
        { header: "Base?", render: (r) => (r.is_base_currency ? "Yes" : "No") },
      ]}
      fields={[
        { name: "code", label: "ISO Code (e.g. USD)", required: true },
        { name: "name", label: "Currency Name", required: true },
        { name: "symbol", label: "Symbol", required: true },
        { name: "exchange_rate_to_base", label: "Exchange Rate to Base", type: "number" },
        { name: "is_base_currency", label: "Set as base currency", type: "checkbox" },
      ]}
      emptyDefaults={{ code: "", name: "", symbol: "", exchange_rate_to_base: 1, is_base_currency: false }}
    />
  );
}
