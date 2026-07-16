import { useEffect, useState } from "react";
import apiClient from "@/api/client";
import LookupCrudPage from "@/components/LookupCrudPage";
import { Branch, City, PaginatedResponse } from "@/types";

export default function BranchesPage() {
  const [cities, setCities] = useState<City[]>([]);

  useEffect(() => {
    apiClient.get<PaginatedResponse<City>>("/cities", { params: { page_size: 200 } }).then(({ data }) => setCities(data.items));
  }, []);

  const cityName = (id?: number | null) => (id ? cities.find((c) => c.id === id)?.name || `#${id}` : "—");

  return (
    <LookupCrudPage<Branch>
      title="Branches"
      description="Operating branches/offices of the company."
      endpoint="/branches"
      permissionModule="branches"
      columns={[
        { header: "Name", render: (r) => <span className="font-medium">{r.name}</span> },
        { header: "Code", render: (r) => <span className="font-mono text-xs">{r.code}</span> },
        { header: "City", render: (r) => cityName(r.city_id) },
        { header: "Head Office", render: (r) => (r.is_head_office ? "Yes" : "No") },
      ]}
      fields={[
        { name: "name", label: "Branch Name", required: true },
        { name: "code", label: "Branch Code", required: true },
        { name: "email", label: "Email" },
        { name: "phone", label: "Phone" },
        { name: "address_line1", label: "Address" },
        { name: "city_id", label: "City", type: "select", options: cities.map((c) => ({ label: c.name, value: c.id })) },
        { name: "is_head_office", label: "This is the head office", type: "checkbox" },
      ]}
      emptyDefaults={{ name: "", code: "", email: "", phone: "", address_line1: "", city_id: null, is_head_office: false }}
    />
  );
}
