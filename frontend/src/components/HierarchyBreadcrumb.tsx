import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronRight } from "lucide-react";
import apiClient from "@/api/client";
import { PropertyDetail } from "@/types";

/**
 * Shows "Building Name > Floor X > Unit 301" above a unit's detail page,
 * so the hierarchy is visible from wherever you land, not just from the
 * Owner's tree view. Read-only, one extra GET for the parent building's
 * title (no new backend endpoint — reuses GET /properties/{id}, which
 * already exists) — only rendered when a property actually has a parent.
 */
export default function HierarchyBreadcrumb({ property }: { property: PropertyDetail }) {
  const navigate = useNavigate();
  const [parentTitle, setParentTitle] = useState<string | null>(null);

  useEffect(() => {
    if (!property.parent_property_id) {
      setParentTitle(null);
      return;
    }
    apiClient.get<PropertyDetail>(`/properties/${property.parent_property_id}`)
      .then(({ data }) => setParentTitle(data.title))
      .catch(() => setParentTitle(null));
  }, [property.parent_property_id]);

  if (!property.parent_property_id) return null;

  return (
    <div className="flex items-center gap-1.5 text-xs text-ink-400 mb-2 flex-wrap">
      <button className="hover:text-ink-700 dark:hover:text-ink-200 hover:underline" onClick={() => navigate(`/properties/${property.parent_property_id}`)}>
        {parentTitle || "Building"}
      </button>
      {(property.floor_label || property.floor_number) && (
        <>
          <ChevronRight size={12} />
          <span>{property.floor_label || `Floor ${property.floor_number}`}</span>
        </>
      )}
      <ChevronRight size={12} />
      <span className="text-ink-600 dark:text-ink-300 font-medium">{property.unit_number ? `Unit ${property.unit_number}` : property.title}</span>
    </div>
  );
}
