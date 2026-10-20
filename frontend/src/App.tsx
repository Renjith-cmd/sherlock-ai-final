import React, { useEffect, useRef, useState } from "react";
import cytoscape from "cytoscape";
import type { Core, EventObject } from "cytoscape";
import {
  Globe,
  Server,
  Mail,
  Link as LinkIcon,
  Play,
  ZoomIn,
  ZoomOut,
  Maximize2,
  CheckCircle,
  XCircle,
  Compass,
  Trash2,
  Edit2,
  Layers,
  Search,
  Filter,
  User,
  Building,
  FileText,
  Hash,
  ArrowRight,
  Plus,
  Copy,
  FolderOpen,
  Activity,
  Download
} from "lucide-react";

interface Entity {
  id: string;
  investigation_id: string;
  type: string;
  label: string;
  properties: Record<string, any>;
  provenance: {
    source: string;
    method: string;
    confidence: number;
    timestamp: string;
  };
}

interface Relationship {
  id: string;
  source_id: string;
  target_id: string;
  type: string;
}

interface TransformMeta {
  id: string;
  name: string;
  description: string;
  accepted_types: string[];
}

interface Candidate {
  entity_type: string;
  label: string;
  relationship_type: string;
  confidence: number;
  properties: Record<string, any>;
}

interface Investigation {
  id: string;
  title: string;
  description?: string;
  tags?: string[];
  created_at: string;
  updated_at: string;
}

export const App: React.FC = () => {
  const [investigationId, setInvestigationId] = useState<string>("");
  const [investigations, setInvestigations] = useState<Investigation[]>([]);
  const [showCaseModal, setShowCaseModal] = useState(false);
  const [selectedEntity, setSelectedEntity] = useState<Entity | null>(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const [selectedNodeCount, setSelectedNodeCount] = useState<number>(0);
  const [transforms, setTransforms] = useState<TransformMeta[]>([]);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [isRunningTransform, setIsRunningTransform] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [currentLayout, setCurrentLayout] = useState<string>("cose");
  const [showAnalyticsModal, setShowAnalyticsModal] = useState(false);
  const [analyticsData, setAnalyticsData] = useState<any>(null);

  const fetchAnalytics = () => {
    if (!investigationId) return;
    fetch(`http://127.0.0.1:8080/api/investigations/${investigationId}/analytics`)
      .then((r) => r.json())
      .then((data) => {
        setAnalyticsData(data);
        setShowAnalyticsModal(true);
      });
  };

  // Context Menu State
  const [contextMenu, setContextMenu] = useState<{
    x: number;
    y: number;
    entity: Entity | null;
  } | null>(null);

  // Link mode state
  const [linkSourceNodeId, setLinkSourceNodeId] = useState<string | null>(null);

  const cyRef = useRef<HTMLDivElement>(null);
  const cyInstance = useRef<Core | null>(null);

  // Load investigations list
  const refreshInvestigations = (selectId?: string) => {
    fetch("http://127.0.0.1:8080/api/investigations")
      .then((res) => res.json())
      .then((data) => {
        setInvestigations(data);
        if (selectId) {
          setInvestigationId(selectId);
        } else if (data.length > 0 && !investigationId) {
          setInvestigationId(data[0].id);
        }
      });
  };

  useEffect(() => {
    refreshInvestigations();
  }, []);

  // Fetch transforms
  useEffect(() => {
    fetch("http://127.0.0.1:8080/api/transforms")
      .then((res) => res.json())
      .then((data) => setTransforms(data))
      .catch(console.error);
  }, []);

  // Cytoscape initialization
  useEffect(() => {
    if (!cyRef.current) return;

    cyInstance.current = cytoscape({
      container: cyRef.current,
      style: [
        {
          selector: "node",
          style: {
            "background-color": "#1e293b",
            "border-width": 2,
            "border-color": "#3b82f6",
            label: "data(label)",
            color: "#f1f5f9",
            "font-size": "11px",
            "font-weight": 600,
            "text-valign": "bottom",
            "text-margin-y": 6,
            width: 40,
            height: 40,
            "overlay-padding": 4,
          },
        },
        {
          selector: "node[type = 'domain']",
          style: { "border-color": "#3b82f6", "background-color": "#1e3a8a" },
        },
        {
          selector: "node[type = 'ip']",
          style: { "border-color": "#10b981", "background-color": "#064e3b" },
        },
        {
          selector: "node[type = 'email']",
          style: { "border-color": "#f59e0b", "background-color": "#78350f" },
        },
        {
          selector: "node[type = 'person']",
          style: { "border-color": "#ec4899", "background-color": "#831843" },
        },
        {
          selector: "node[type = 'organization']",
          style: { "border-color": "#a855f7", "background-color": "#581c87" },
        },
        {
          selector: "node[type = 'file_hash']",
          style: { "border-color": "#64748b", "background-color": "#334155" },
        },
        {
          selector: "node:selected",
          style: {
            "border-color": "#38bdf8",
            "border-width": 4,
          },
        },
        {
          selector: "node.highlighted",
          style: {
            "border-color": "#eab308",
            "border-width": 4,
            "background-color": "#713f12",
          },
        },
        {
          selector: "edge",
          style: {
            width: 2,
            "line-color": "#475569",
            "target-arrow-color": "#475569",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            label: "data(label)",
            color: "#94a3b8",
            "font-size": "9px",
            "text-rotation": "autorotate",
            "text-background-opacity": 0.8,
            "text-background-color": "#0f172a",
            "text-background-padding": "2px",
          },
        },
        {
          selector: "edge:selected",
          style: {
            width: 4,
            "line-color": "#38bdf8",
            "target-arrow-color": "#38bdf8",
            color: "#38bdf8",
          },
        },
      ],
      layout: { name: "cose", animate: false },
    });

    const cy = cyInstance.current;

    // Selection handlers
    cy.on("select", "node", (evt: EventObject) => {
      const selected = cy.$("node:selected");
      setSelectedNodeCount(selected.length);
      if (selected.length === 1) {
        setSelectedEntity(evt.target.data("entity"));
      } else {
        setSelectedEntity(null);
      }
      setSelectedEdgeId(null);
    });

    cy.on("unselect", "node", () => {
      const selected = cy.$("node:selected");
      setSelectedNodeCount(selected.length);
      if (selected.length === 1) {
        setSelectedEntity(selected[0].data("entity"));
      } else {
        setSelectedEntity(null);
      }
    });

    cy.on("select", "edge", (evt: EventObject) => {
      setSelectedEdgeId(evt.target.id());
      setSelectedEntity(null);
    });

    cy.on("unselect", "edge", () => {
      setSelectedEdgeId(null);
    });

    // Right-click Context Menu on Nodes
    cy.on("cxttap", "node", (evt: EventObject) => {
      evt.originalEvent.preventDefault();
      const node = evt.target;
      const renderedPos = node.renderedPosition();
      setContextMenu({
        x: renderedPos.x + 280,
        y: renderedPos.y + 60,
        entity: node.data("entity"),
      });
    });

    cy.on("tap", (evt: EventObject) => {
      if (evt.target === cy) {
        setContextMenu(null);
      }
    });

    return () => {
      if (cyInstance.current) {
        cyInstance.current.destroy();
      }
    };
  }, []);

  // Load Graph elements
  const loadGraph = (invId: string, layoutName: string = currentLayout) => {
    if (!invId || !cyInstance.current) return;
    fetch(`http://127.0.0.1:8080/api/investigations/${invId}/graph`)
      .then((res) => res.json())
      .then((data) => {
        const cy = cyInstance.current!;
        cy.elements().remove();

        data.nodes.forEach((n: Entity) => {
          cy.add({
            group: "nodes",
            data: { id: n.id, label: n.label, type: n.type, entity: n },
          });
        });

        data.edges.forEach((e: Relationship) => {
          cy.add({
            group: "edges",
            data: { id: e.id, source: e.source_id, target: e.target_id, label: e.type },
          });
        });

        applyLayout(layoutName);
      });
  };

  const applyLayout = (name: string) => {
    if (!cyInstance.current) return;
    setCurrentLayout(name);
    cyInstance.current.layout({ name, animate: true } as any).run();
  };

  useEffect(() => {
    if (investigationId) {
      loadGraph(investigationId);
    }
  }, [investigationId]);

  // Search & Type Filtering
  useEffect(() => {
    if (!cyInstance.current) return;
    const cy = cyInstance.current;
    cy.batch(() => {
      cy.nodes().forEach((node) => {
        const matchesType = typeFilter === "all" || node.data("type") === typeFilter;
        const matchesSearch =
          !searchTerm ||
          node.data("label").toLowerCase().includes(searchTerm.toLowerCase());

        if (matchesType) {
          node.style("display", "element");
        } else {
          node.style("display", "none");
        }

        if (searchTerm && matchesSearch && matchesType) {
          node.addClass("highlighted");
        } else {
          node.removeClass("highlighted");
        }
      });
    });
  }, [searchTerm, typeFilter]);

  // Add Entity manually
  const handleAddEntity = (type: string, defaultLabel: string) => {
    const label = window.prompt(`Enter ${type} value:`, defaultLabel);
    if (!label || !investigationId) return;

    fetch(`http://127.0.0.1:8080/api/investigations/${investigationId}/entities`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ type, label, properties: {} }),
    })
      .then((res) => res.json())
      .then((newEntity) => {
        const cy = cyInstance.current;
        if (cy) {
          cy.add({
            group: "nodes",
            data: { id: newEntity.id, label: newEntity.label, type: newEntity.type, entity: newEntity },
          });
          applyLayout(currentLayout);
        }
      });
  };

  // Investigation Management Actions
  const handleCreateInvestigation = () => {
    const title = window.prompt("New Investigation Title:", "Operation New Horizon");
    if (!title) return;
    fetch("http://127.0.0.1:8080/api/investigations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, description: "Active OSINT Workspace" }),
    })
      .then((r) => r.json())
      .then((newInv) => {
        refreshInvestigations(newInv.id);
        setShowCaseModal(false);
      });
  };

  const handleDuplicateInvestigation = (idToDup: string) => {
    const target = investigations.find((i) => i.id === idToDup);
    const newTitle = window.prompt("Duplicate Investigation As:", target ? `${target.title} (Clone)` : "Investigation Copy");
    if (!newTitle) return;

    fetch(`http://127.0.0.1:8080/api/investigations/${idToDup}/duplicate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: newTitle }),
    })
      .then((r) => r.json())
      .then((cloned) => {
        refreshInvestigations(cloned.id);
        setShowCaseModal(false);
      });
  };

  const handleDeleteInvestigation = (idToDel: string) => {
    if (!window.confirm("Are you sure you want to permanently delete this investigation and its entire graph?")) return;
    fetch(`http://127.0.0.1:8080/api/investigations/${idToDel}`, { method: "DELETE" })
      .then((r) => r.json())
      .then(() => {
        const remaining = investigations.filter((i) => i.id !== idToDel);
        setInvestigations(remaining);
        if (remaining.length > 0) {
          setInvestigationId(remaining[0].id);
        }
      });
  };

  // Delete Entity
  const handleDeleteEntity = (entityId: string) => {
    if (!window.confirm("Are you sure you want to delete this entity from the investigation?")) return;
    fetch(`http://127.0.0.1:8080/api/entities/${entityId}`, { method: "DELETE" })
      .then((res) => res.json())
      .then(() => {
        cyInstance.current?.$(`#${entityId}`).remove();
        setSelectedEntity(null);
        setContextMenu(null);
      });
  };

  // Delete Edge
  const handleDeleteEdge = (edgeId: string) => {
    if (!window.confirm("Delete relationship link?")) return;
    fetch(`http://127.0.0.1:8080/api/relationships/${edgeId}`, { method: "DELETE" })
      .then((res) => res.json())
      .then(() => {
        cyInstance.current?.$(`#${edgeId}`).remove();
        setSelectedEdgeId(null);
      });
  };

  // Rename Entity
  const handleRenameEntity = (entity: Entity) => {
    const newLabel = window.prompt("Edit entity label:", entity.label);
    if (!newLabel || newLabel === entity.label) return;

    fetch(`http://127.0.0.1:8080/api/entities/${entity.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ label: newLabel }),
    })
      .then((r) => r.json())
      .then((updated) => {
        const node = cyInstance.current?.$(`#${entity.id}`);
        if (node) {
          node.data("label", updated.label);
          node.data("entity", updated);
        }
        setSelectedEntity(updated);
        setContextMenu(null);
      });
  };

  // Link Mode Handler
  const handleStartLinking = (sourceId: string) => {
    setLinkSourceNodeId(sourceId);
    setContextMenu(null);
  };

  const handleFinishLinking = (targetId: string) => {
    if (!linkSourceNodeId || linkSourceNodeId === targetId || !investigationId) {
      setLinkSourceNodeId(null);
      return;
    }

    const relType = window.prompt("Enter relationship label:", "CONNECTED_TO") || "CONNECTED_TO";

    fetch(`http://127.0.0.1:8080/api/investigations/${investigationId}/relationships`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source_id: linkSourceNodeId,
        target_id: targetId,
        type: relType,
      }),
    })
      .then((r) => r.json())
      .then((rel) => {
        cyInstance.current?.add({
          group: "edges",
          data: { id: rel.id, source: rel.source_id, target: rel.target_id, label: rel.type },
        });
        setLinkSourceNodeId(null);
      });
  };

  // Run Transform
  const handleRunTransform = (tId: string) => {
    if (!selectedEntity || !investigationId) return;
    setIsRunningTransform(true);
    setContextMenu(null);
    fetch(`http://127.0.0.1:8080/api/investigations/${investigationId}/transforms/execute`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ transform_id: tId, entity_id: selectedEntity.id }),
    })
      .then((r) => r.json())
      .then((cands) => {
        setCandidates(cands);
        setIsRunningTransform(false);
      })
      .catch((err) => {
        console.error(err);
        setIsRunningTransform(false);
      });
  };

  // Commit Candidates to Graph
  const handleMergeCandidates = () => {
    if (!selectedEntity || !investigationId || candidates.length === 0) return;
    fetch(`http://127.0.0.1:8080/api/investigations/${investigationId}/transforms/merge`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ entity_id: selectedEntity.id, candidates }),
    })
      .then((r) => r.json())
      .then(() => {
        setCandidates([]);
        loadGraph(investigationId);
      });
  };

  const activeInv = investigations.find((i) => i.id === investigationId);

  return (
    <>
      <header className="app-header">
        <div className="brand-badge">
          <Compass className="brand-icon" size={22} />
          <span>ARKANA INVESTIGATOR</span>
        </div>

        {/* Search & Filter Bar */}
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <div style={{ display: "flex", alignItems: "center", background: "#1e293b", padding: "4px 8px", borderRadius: "6px", border: "1px solid #2a3749" }}>
            <Search size={14} color="#94a3b8" style={{ marginRight: "6px" }} />
            <input
              type="text"
              placeholder="Search graph entities..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              style={{ background: "transparent", border: "none", color: "#f1f5f9", fontSize: "12px", outline: "none", width: "160px" }}
            />
          </div>

          <div style={{ display: "flex", alignItems: "center", background: "#1e293b", padding: "4px 8px", borderRadius: "6px", border: "1px solid #2a3749" }}>
            <Filter size={14} color="#94a3b8" style={{ marginRight: "6px" }} />
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              style={{ background: "transparent", border: "none", color: "#f1f5f9", fontSize: "12px", outline: "none" }}
            >
              <option value="all">All Types</option>
              <option value="domain">Domain</option>
              <option value="ip">IP</option>
              <option value="email">Email</option>
              <option value="person">Person</option>
              <option value="organization">Organization</option>
            </select>
          </div>
        </div>

        {/* Investigation Selector & Modal Launcher */}
        <div className="top-actions">
          {/* Export Actions */}
          <button
            className="tool-btn"
            style={{ background: "#1e293b", border: "1px solid #2a3749" }}
            title="Export Graph to JSON"
            onClick={() => {
              if (investigationId) {
                window.open(`http://127.0.0.1:8080/api/investigations/${investigationId}/export/json`, "_blank");
              }
            }}
          >
            <Download size={13} color="#10b981" /> JSON
          </button>
          <button
            className="tool-btn"
            style={{ background: "#1e293b", border: "1px solid #2a3749" }}
            title="Generate Forensic Report"
            onClick={() => {
              if (investigationId) {
                window.open(`http://127.0.0.1:8080/api/investigations/${investigationId}/report`, "_blank");
              }
            }}
          >
            <FileText size={13} color="#f59e0b" /> Report
          </button>

          <button
            className="tool-btn"
            style={{ background: "#1e293b", border: "1px solid #2a3749" }}
            onClick={() => setShowCaseModal(true)}
          >
            <FolderOpen size={14} color="#38bdf8" /> Cases ({investigations.length})
          </button>
          <button
            className="tool-btn"
            style={{ background: "#059669", color: "#fff" }}
            onClick={handleCreateInvestigation}
          >
            <Plus size={14} /> New Case
          </button>
        </div>
      </header>

      {/* Case Management Modal */}
      {showCaseModal && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: "rgba(0,0,0,0.75)",
            zIndex: 100,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <div
            style={{
              background: "#161f2d",
              border: "1px solid #2a3749",
              borderRadius: "8px",
              width: "600px",
              maxHeight: "80vh",
              display: "flex",
              flexDirection: "column",
              boxShadow: "0 12px 32px rgba(0,0,0,0.8)",
            }}
          >
            <div style={{ padding: "16px", borderBottom: "1px solid #2a3749", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ fontWeight: 700, fontSize: "15px" }}>Investigation Case Management</div>
              <button
                onClick={() => setShowCaseModal(false)}
                style={{ background: "transparent", border: "none", color: "#94a3b8", cursor: "pointer", fontSize: "16px" }}
              >
                ✕
              </button>
            </div>
            <div style={{ padding: "16px", overflowY: "auto", display: "flex", flexDirection: "column", gap: "10px" }}>
              {investigations.map((inv) => (
                <div
                  key={inv.id}
                  style={{
                    background: inv.id === investigationId ? "#1e293b" : "#0f172a",
                    border: `1px solid ${inv.id === investigationId ? "#3b82f6" : "#2a3749"}`,
                    padding: "12px",
                    borderRadius: "6px",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 600, fontSize: "14px", color: inv.id === investigationId ? "#38bdf8" : "#f1f5f9" }}>
                      {inv.title} {inv.id === investigationId && <span style={{ fontSize: "10px", color: "#10b981", background: "#064e3b", padding: "2px 6px", borderRadius: "4px" }}>ACTIVE</span>}
                    </div>
                    <div style={{ fontSize: "11px", color: "#94a3b8", marginTop: "2px" }}>
                      Created: {new Date(inv.created_at).toLocaleString()} | ID: {inv.id.slice(0, 8)}...
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: "6px" }}>
                    {inv.id !== investigationId && (
                      <button
                        className="tool-btn"
                        style={{ background: "#2563eb", color: "#fff" }}
                        onClick={() => {
                          setInvestigationId(inv.id);
                          setShowCaseModal(false);
                        }}
                      >
                        Open
                      </button>
                    )}
                    <button
                      className="tool-btn"
                      style={{ background: "#334155" }}
                      title="Duplicate Investigation"
                      onClick={() => handleDuplicateInvestigation(inv.id)}
                    >
                      <Copy size={13} />
                    </button>
                    <button
                      className="tool-btn"
                      style={{ background: "#7f1d1d", color: "#fca5a5" }}
                      title="Delete Investigation"
                      onClick={() => handleDeleteInvestigation(inv.id)}
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Link creation banner */}
      {linkSourceNodeId && (
        <div style={{ background: "#0284c7", color: "#fff", padding: "6px 16px", fontSize: "12px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span><b>Link Mode:</b> Click on any target entity to create a relationship.</span>
          <button
            onClick={() => setLinkSourceNodeId(null)}
            style={{ background: "#0369a1", border: "none", color: "#fff", padding: "2px 8px", borderRadius: "4px", cursor: "pointer" }}
          >
            Cancel
          </button>
        </div>
      )}

      <div className="workbench-body">
        {/* Left Palette */}
        <aside className="nav-sidebar">
          <div className="sidebar-section">
            <div className="sidebar-title">Case Information</div>
            <div style={{ fontSize: "13px", fontWeight: 700, color: "#38bdf8", marginBottom: "4px" }}>
              {activeInv?.title || "Active Case"}
            </div>
            <div style={{ fontSize: "11px", color: "#94a3b8" }}>
              {activeInv?.description || "Graph Link Analysis"}
            </div>
          </div>

          <div className="sidebar-section">
            <div className="sidebar-title">Add Entity to Graph</div>
            <div className="palette-grid">
              <button className="palette-btn" onClick={() => handleAddEntity("domain", "target.com")}>
                <Globe size={14} color="#3b82f6" /> Domain
              </button>
              <button className="palette-btn" onClick={() => handleAddEntity("ip", "1.1.1.1")}>
                <Server size={14} color="#10b981" /> IP Address
              </button>
              <button className="palette-btn" onClick={() => handleAddEntity("email", "admin@target.com")}>
                <Mail size={14} color="#f59e0b" /> Email
              </button>
              <button className="palette-btn" onClick={() => handleAddEntity("url", "https://target.com")}>
                <LinkIcon size={14} color="#8b5cf6" /> URL
              </button>
              <button className="palette-btn" onClick={() => handleAddEntity("person", "John Doe")}>
                <User size={14} color="#ec4899" /> Person
              </button>
              <button className="palette-btn" onClick={() => handleAddEntity("organization", "Acme Corp")}>
                <Building size={14} color="#a855f7" /> Organization
              </button>
              <button className="palette-btn" onClick={() => handleAddEntity("document", "Doc-01.pdf")}>
                <FileText size={14} color="#06b6d4" /> Document
              </button>
              <button className="palette-btn" onClick={() => handleAddEntity("file_hash", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")}>
                <Hash size={14} color="#64748b" /> File Hash
              </button>
            </div>
          </div>

          {/* Active Entity Transforms */}
          <div className="sidebar-section" style={{ flex: 1, overflowY: "auto" }}>
            <div className="sidebar-title">Available Transforms</div>
            {selectedEntity ? (
              <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                <div style={{ fontSize: "11px", color: "#94a3b8", marginBottom: "4px" }}>
                  Pivoting from: <b>{selectedEntity.label}</b> ({selectedEntity.type})
                </div>
                {transforms
                  .filter((t) => t.accepted_types.includes(selectedEntity.type))
                  .map((t) => (
                    <button
                      key={t.id}
                      className="palette-btn"
                      style={{ justifyContent: "space-between" }}
                      disabled={isRunningTransform}
                      onClick={() => handleRunTransform(t.id)}
                    >
                      <span>{t.name}</span>
                      <Play size={12} color="#10b981" />
                    </button>
                  ))}
              </div>
            ) : selectedNodeCount > 1 ? (
              <div style={{ fontSize: "12px", color: "#94a3b8" }}>
                {selectedNodeCount} entities selected (multi-selection active).
              </div>
            ) : (
              <div style={{ fontSize: "12px", color: "#64748b" }}>
                Select a node on the canvas to view compatible transforms.
              </div>
            )}
          </div>
        </aside>

        {/* Central Canvas */}
        <main className="canvas-wrapper">
          <div className="graph-toolbar">
            <button className="tool-btn" onClick={() => cyInstance.current?.zoom(cyInstance.current.zoom() * 1.2)}>
              <ZoomIn size={14} /> Zoom In
            </button>
            <button className="tool-btn" onClick={() => cyInstance.current?.zoom(cyInstance.current.zoom() * 0.8)}>
              <ZoomOut size={14} /> Zoom Out
            </button>
            <button className="tool-btn" onClick={() => cyInstance.current?.fit(undefined, 30)}>
              <Maximize2 size={14} /> Fit View
            </button>

            {/* Layout Algorithms */}
            <div style={{ display: "flex", alignItems: "center", gap: "4px", borderLeft: "1px solid #334155", paddingLeft: "6px" }}>
              <Layers size={14} color="#94a3b8" />
              <select
                value={currentLayout}
                onChange={(e) => applyLayout(e.target.value)}
                style={{ background: "#1e293b", border: "none", color: "#f1f5f9", fontSize: "11px", padding: "2px 4px", borderRadius: "4px" }}
              >
                <option value="cose">Force-Directed (CoSE)</option>
                <option value="circle">Circular</option>
                <option value="grid">Grid</option>
                <option value="breadthfirst">Hierarchical (Tree)</option>
                <option value="concentric">Concentric</option>
              </select>
            </div>

            {/* Analytics Launcher */}
            <button
              className="tool-btn"
              style={{ borderLeft: "1px solid #334155", paddingLeft: "8px", color: "#38bdf8" }}
              onClick={fetchAnalytics}
              title="Graph Topology & Centrality Analytics"
            >
              <Activity size={14} /> Analytics
            </button>
          </div>

          {/* Graph Analytics Modal */}
          {showAnalyticsModal && analyticsData && (
            <div
              style={{
                position: "fixed",
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                background: "rgba(0,0,0,0.75)",
                zIndex: 100,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <div
                style={{
                  background: "#161f2d",
                  border: "1px solid #2a3749",
                  borderRadius: "8px",
                  width: "520px",
                  maxHeight: "80vh",
                  display: "flex",
                  flexDirection: "column",
                  boxShadow: "0 12px 32px rgba(0,0,0,0.8)",
                }}
              >
                <div style={{ padding: "16px", borderBottom: "1px solid #2a3749", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div style={{ fontWeight: 700, fontSize: "15px", display: "flex", alignItems: "center", gap: "8px" }}>
                    <Activity size={18} color="#38bdf8" /> Graph Topology Metrics
                  </div>
                  <button
                    onClick={() => setShowAnalyticsModal(false)}
                    style={{ background: "transparent", border: "none", color: "#94a3b8", cursor: "pointer", fontSize: "16px" }}
                  >
                    ✕
                  </button>
                </div>
                <div style={{ padding: "16px", display: "flex", flexDirection: "column", gap: "12px" }}>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "10px" }}>
                    <div style={{ background: "#0f172a", padding: "12px", borderRadius: "6px", textAlign: "center", border: "1px solid #2a3749" }}>
                      <div style={{ fontSize: "20px", fontWeight: 700, color: "#38bdf8" }}>{analyticsData.node_count}</div>
                      <div style={{ fontSize: "11px", color: "#94a3b8", textTransform: "uppercase" }}>Nodes</div>
                    </div>
                    <div style={{ background: "#0f172a", padding: "12px", borderRadius: "6px", textAlign: "center", border: "1px solid #2a3749" }}>
                      <div style={{ fontSize: "20px", fontWeight: 700, color: "#10b981" }}>{analyticsData.edge_count}</div>
                      <div style={{ fontSize: "11px", color: "#94a3b8", textTransform: "uppercase" }}>Edges</div>
                    </div>
                    <div style={{ background: "#0f172a", padding: "12px", borderRadius: "6px", textAlign: "center", border: "1px solid #2a3749" }}>
                      <div style={{ fontSize: "20px", fontWeight: 700, color: "#f59e0b" }}>{analyticsData.connected_components_count}</div>
                      <div style={{ fontSize: "11px", color: "#94a3b8", textTransform: "uppercase" }}>Components</div>
                    </div>
                  </div>

                  <div style={{ marginTop: "8px" }}>
                    <div style={{ fontSize: "12px", fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", marginBottom: "8px" }}>
                      Top Degree Centrality Hubs
                    </div>
                    {analyticsData.top_hubs.length === 0 ? (
                      <div style={{ fontSize: "12px", color: "#64748b" }}>No hubs detected in graph.</div>
                    ) : (
                      analyticsData.top_hubs.map((hub: any) => (
                        <div
                          key={hub.id}
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center",
                            background: "#0f172a",
                            padding: "8px 12px",
                            borderRadius: "4px",
                            border: "1px solid #2a3749",
                            marginBottom: "6px",
                          }}
                        >
                          <div>
                            <span style={{ fontWeight: 600, fontSize: "13px" }}>{hub.label}</span>
                            <span style={{ fontSize: "11px", color: "#94a3b8", marginLeft: "6px" }}>({hub.type})</span>
                          </div>
                          <span style={{ fontSize: "12px", color: "#38bdf8", fontWeight: 700 }}>
                            Degree: {hub.degree}
                          </span>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          <div
            id="cy-container"
            ref={cyRef}
            onClick={() => {
              if (linkSourceNodeId && selectedEntity) {
                handleFinishLinking(selectedEntity.id);
              }
            }}
          />

          {/* Context Menu Popup */}
          {contextMenu && (
            <div
              style={{
                position: "absolute",
                left: `${contextMenu.x}px`,
                top: `${contextMenu.y}px`,
                background: "#1e293b",
                border: "1px solid #334155",
                borderRadius: "6px",
                padding: "6px",
                display: "flex",
                flexDirection: "column",
                gap: "4px",
                zIndex: 50,
                boxShadow: "0 8px 24px rgba(0,0,0,0.6)",
                minWidth: "160px",
              }}
            >
              <div style={{ padding: "4px 8px", fontSize: "11px", fontWeight: 700, color: "#94a3b8", borderBottom: "1px solid #334155" }}>
                {contextMenu.entity?.label}
              </div>
              <button
                className="tool-btn"
                onClick={() => contextMenu.entity && handleStartLinking(contextMenu.entity.id)}
              >
                <ArrowRight size={14} color="#38bdf8" /> Connect Relationship
              </button>
              <button
                className="tool-btn"
                onClick={() => contextMenu.entity && handleRenameEntity(contextMenu.entity)}
              >
                <Edit2 size={14} color="#fbbf24" /> Rename Entity
              </button>
              <button
                className="tool-btn"
                style={{ color: "#f87171" }}
                onClick={() => contextMenu.entity && handleDeleteEntity(contextMenu.entity.id)}
              >
                <Trash2 size={14} /> Delete from Graph
              </button>
            </div>
          )}

          {/* Bottom Candidates Drawer */}
          {candidates.length > 0 && (
            <div className="transform-drawer">
              <div className="drawer-header">
                <span>Discovered Candidates ({candidates.length})</span>
                <div style={{ display: "flex", gap: "8px" }}>
                  <button
                    className="palette-btn"
                    style={{ background: "#10b981", border: "none", color: "#fff", padding: "4px 8px" }}
                    onClick={handleMergeCandidates}
                  >
                    <CheckCircle size={14} /> Add to Graph
                  </button>
                  <button
                    className="palette-btn"
                    style={{ background: "#ef4444", border: "none", color: "#fff", padding: "4px 8px" }}
                    onClick={() => setCandidates([])}
                  >
                    <XCircle size={14} /> Discard
                  </button>
                </div>
              </div>
              <div className="candidate-list">
                {candidates.map((c, idx) => (
                  <div key={idx} className="candidate-item">
                    <div>
                      <b>{c.label}</b> <span style={{ color: "#94a3b8", fontSize: "11px" }}>({c.entity_type})</span>
                    </div>
                    <span style={{ fontSize: "11px", color: "#3b82f6" }}>[{c.relationship_type}]</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </main>

        {/* Right Inspector */}
        <aside className="inspector-panel">
          <div className="inspector-header">Inspector</div>
          {selectedEntity ? (
            <div className="inspector-content">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span className="prop-label">Entity Actions</span>
                <div style={{ display: "flex", gap: "6px" }}>
                  <button
                    className="tool-btn"
                    style={{ padding: "4px", background: "#334155" }}
                    title="Rename Entity"
                    onClick={() => handleRenameEntity(selectedEntity)}
                  >
                    <Edit2 size={12} />
                  </button>
                  <button
                    className="tool-btn"
                    style={{ padding: "4px", background: "#7f1d1d", color: "#fca5a5" }}
                    title="Delete Entity"
                    onClick={() => handleDeleteEntity(selectedEntity.id)}
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
              </div>
              <div className="property-group">
                <span className="prop-label">Label</span>
                <div className="prop-value">{selectedEntity.label}</div>
              </div>
              <div className="property-group">
                <span className="prop-label">Type</span>
                <div className="prop-value">{selectedEntity.type}</div>
              </div>
              <div className="property-group">
                <span className="prop-label">Internal ID</span>
                <div className="prop-value" style={{ fontSize: "11px" }}>{selectedEntity.id}</div>
              </div>
              <div className="property-group">
                <span className="prop-label">Provenance Source</span>
                <div className="prop-value">{selectedEntity.provenance?.source || "manual"}</div>
              </div>
              <div className="property-group">
                <span className="prop-label">Acquisition Method</span>
                <div className="prop-value">{selectedEntity.provenance?.method || "direct"}</div>
              </div>
              <div className="property-group">
                <span className="prop-label">Confidence</span>
                <div className="prop-value">{selectedEntity.provenance?.confidence ?? 1.0}</div>
              </div>
              <div className="property-group">
                <span className="prop-label">Observed Timestamp</span>
                <div className="prop-value" style={{ fontSize: "11px" }}>
                  {selectedEntity.provenance?.timestamp || "N/A"}
                </div>
              </div>

              {/* Supporting Evidence Section */}
              <div style={{ marginTop: "10px", borderTop: "1px solid #2a3749", paddingTop: "10px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                  <span className="prop-label">Evidence & Provenance</span>
                  <button
                    className="tool-btn"
                    style={{ background: "#1e293b", border: "1px solid #2a3749", padding: "2px 6px", fontSize: "11px" }}
                    onClick={() => {
                      const sourceId = window.prompt("Source identifier (e.g. CERT Advisory, Log entry):", "Analyst Note");
                      if (!sourceId) return;
                      const notes = window.prompt("Notes or evidence quote:", "Verified by human analyst");
                      fetch(`http://127.0.0.1:8080/api/investigations/${investigationId}/entities/${selectedEntity.id}/evidence`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ source_identifier: sourceId, user_notes: notes }),
                      })
                        .then((r) => r.json())
                        .then(() => alert("Evidence attached to entity successfully."));
                    }}
                  >
                    + Attach
                  </button>
                </div>
                <div style={{ fontSize: "11px", color: "#94a3b8", fontStyle: "italic" }}>
                  Evidence is immutably pinned with cryptographic source provenance and audit timestamps.
                </div>
              </div>
            </div>
          ) : selectedEdgeId ? (
            <div className="inspector-content">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span className="prop-label">Relationship Selected</span>
                <button
                  className="tool-btn"
                  style={{ padding: "4px", background: "#7f1d1d", color: "#fca5a5" }}
                  title="Delete Relationship"
                  onClick={() => handleDeleteEdge(selectedEdgeId)}
                >
                  <Trash2 size={12} /> Delete Link
                </button>
              </div>
              <div className="property-group">
                <span className="prop-label">Edge ID</span>
                <div className="prop-value" style={{ fontSize: "11px" }}>{selectedEdgeId}</div>
              </div>
            </div>
          ) : (
            <div style={{ padding: "14px", fontSize: "12px", color: "#64748b" }}>
              Click on an entity or relationship on the canvas to inspect properties, provenance, or edit attributes.
            </div>
          )}
        </aside>
      </div>
    </>
  );
};

export default App;
