import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Building2, ChevronRight, ChevronDown, DoorOpen, User } from "lucide-react";
import { PropertyHierarchyTree, HierarchyPropertyNode, HierarchyFloorNode, HierarchyUnitNode } from "@/types";

const STATUS_TONE: Record<string, string> = {
  available: "badge-active", leased: "badge-active", occupied: "badge-active",
  reserved: "badge-warn", under_maintenance: "badge-warn", off_market: "badge-inactive",
};

export default function PropertyHierarchyTreeView({ tree }: { tree: PropertyHierarchyTree }) {
  if (tree.properties.length === 0) {
    return <p className="text-sm text-ink-400 py-6 text-center">No properties recorded for this owner yet.</p>;
  }
  return (
    <div className="space-y-1">
      {tree.properties.map((p) => <PropertyNode key={p.id} node={p} />)}
    </div>
  );
}

function TreeRow({ icon, label, sublabel, badge, indent, expandable, expanded, onToggle, onClick }: {
  icon: React.ReactNode; label: string; sublabel?: string; badge?: React.ReactNode; indent: number;
  expandable?: boolean; expanded?: boolean; onToggle?: () => void; onClick?: () => void;
}) {
  return (
    <div
      className={`flex items-center gap-2 py-2 px-2 rounded-md hover:bg-ink-50 dark:hover:bg-ink-800/40 ${onClick ? "cursor-pointer" : ""}`}
      style={{ paddingLeft: `${8 + indent * 22}px` }}
      onClick={onClick}
    >
      {expandable ? (
        <button
          type="button"
          className="text-ink-400 hover:text-ink-700 dark:hover:text-ink-200 shrink-0"
          onClick={(e) => { e.stopPropagation(); onToggle?.(); }}
        >
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </button>
      ) : (
        <span className="w-[14px] shrink-0" />
      )}
      <span className="text-ink-400 shrink-0">{icon}</span>
      <span className="text-sm font-medium truncate">{label}</span>
      {sublabel && <span className="text-xs text-ink-400 truncate">{sublabel}</span>}
      <span className="ml-auto shrink-0">{badge}</span>
    </div>
  );
}

function PropertyNode({ node }: { node: HierarchyPropertyNode }) {
  const navigate = useNavigate();
  const [expanded, setExpanded] = useState(true);
  const hasChildren = node.floors.length > 0;

  return (
    <div>
      <TreeRow
        indent={0}
        icon={<Building2 size={15} />}
        label={node.title}
        sublabel={node.property_code}
        expandable={hasChildren}
        expanded={expanded}
        onToggle={() => setExpanded((v) => !v)}
        onClick={() => navigate(`/properties/${node.id}`)}
        badge={!hasChildren && node.active_contract ? (
          <span className="text-xs text-ink-500">{node.active_contract.tenant_name}</span>
        ) : !hasChildren ? (
          <span className="badge-inactive">Vacant</span>
        ) : null}
      />
      {hasChildren && expanded && node.floors.map((f) => <FloorNode key={f.id ?? "unassigned"} node={f} />)}
    </div>
  );
}

function FloorNode({ node }: { node: HierarchyFloorNode }) {
  const [expanded, setExpanded] = useState(true);
  return (
    <div>
      <TreeRow
        indent={1}
        icon={<Building2 size={13} />}
        label={node.floor_name || `Floor ${node.floor_number}`}
        sublabel={`${node.units.length} unit(s)`}
        expandable={node.units.length > 0}
        expanded={expanded}
        onToggle={() => setExpanded((v) => !v)}
      />
      {expanded && node.units.map((u) => <UnitNode key={u.id} node={u} />)}
    </div>
  );
}

function UnitNode({ node }: { node: HierarchyUnitNode }) {
  const navigate = useNavigate();
  return (
    <TreeRow
      indent={2}
      icon={<DoorOpen size={13} />}
      label={node.unit_number ? `Unit ${node.unit_number}` : `Unit #${node.id}`}
      sublabel={node.unit_type}
      onClick={() => navigate(`/properties/${node.id}`)}
      badge={node.active_contract ? (
        <span className="flex items-center gap-1.5 text-xs text-ink-500">
          <User size={11} /> {node.active_contract.tenant_name}
        </span>
      ) : (
        <span className={STATUS_TONE[node.availability_status] || "badge-inactive"}>{node.availability_status.replace("_", " ")}</span>
      )}
    />
  );
}
