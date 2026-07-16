import LookupCrudPage from "@/components/LookupCrudPage";
import { Country } from "@/types";

export default function CountriesPage() {
  return (
    <LookupCrudPage<Country>
      title="Countries"
      description="Reference list of countries used across branches, cities, and company addresses."
      endpoint="/countries"
      permissionModule="countries"
      columns={[
        { header: "Name", render: (r) => <span className="font-medium">{r.name}</span> },
        { header: "ISO-2", render: (r) => r.iso_code2 },
        { header: "ISO-3", render: (r) => r.iso_code3 },
        { header: "Phone Code", render: (r) => r.phone_code || "—" },
      ]}
      fields={[
        { name: "name", label: "Country Name", required: true },
        { name: "iso_code2", label: "ISO Code (2-letter)", required: true },
        { name: "iso_code3", label: "ISO Code (3-letter)", required: true },
        { name: "phone_code", label: "Phone Code" },
      ]}
      emptyDefaults={{ name: "", iso_code2: "", iso_code3: "", phone_code: "" }}
    />
  );
}
