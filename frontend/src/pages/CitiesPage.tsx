import { useEffect, useState } from "react";
import apiClient from "@/api/client";
import LookupCrudPage from "@/components/LookupCrudPage";
import { City, Country, PaginatedResponse } from "@/types";

export default function CitiesPage() {
  const [countries, setCountries] = useState<Country[]>([]);

  useEffect(() => {
    apiClient.get<PaginatedResponse<Country>>("/countries", { params: { page_size: 200 } }).then(({ data }) => setCountries(data.items));
  }, []);

  const countryName = (id: number) => countries.find((c) => c.id === id)?.name || `#${id}`;

  return (
    <LookupCrudPage<City>
      title="Cities"
      description="Cities grouped by country, used for branches and company addresses."
      endpoint="/cities"
      permissionModule="cities"
      columns={[
        { header: "Name", render: (r) => <span className="font-medium">{r.name}</span> },
        { header: "Country", render: (r) => countryName(r.country_id) },
      ]}
      fields={[
        { name: "name", label: "City Name", required: true },
        { name: "country_id", label: "Country", type: "select", required: true, options: countries.map((c) => ({ label: c.name, value: c.id })) },
      ]}
      emptyDefaults={{ name: "", country_id: null }}
    />
  );
}
