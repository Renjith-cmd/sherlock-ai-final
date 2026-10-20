import React, { useEffect, useRef, useState } from "react";
import cytoscape from "cytoscape";
import type { Core } from "cytoscape";
import {
  Globe,
  Server,
  Mail,
  Link as LinkIcon,
  Play,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Database,
  CheckCircle,
  XCircle,
  Compass
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

export const App: React.FC = () => {
  const [investigationId, setInvestigationId] = useState<string>("");
  const [investigations, setInvestigations] = useState<any[]>([]);
  const [selectedEntity, setSelectedEntity] = useState<Entity | null>(null);
  const [transforms, setTransforms] = useState<TransformMeta[]>([]);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [isRunningTransform, setIsRunningTransform] = useState(false);

  const cyRef = useRef<HTMLDivElement>(null);
  const cyInstance = useRef<Core | null>(null);

  // Initialize or fetch default investigation
  useEffect(() => {
    fetch("http://127.0.0.1:8080/api/investigations")
      .then((res) => res.json())
      .then((data) => {
        setInvestigations(data);
        if (data.length > 0) {
          setInvestigationId(data[0].id);
        } else {
          // Create initial investigation
          fetch("http://127.0.0.1:8080/api/investigations", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ title: "Operation Sovereign Link", description: "Primary OSINT workbench" }),
          })
            .then((r) => r.json())
            .then((newInv) => {
              setInvestigations([newInv]);
              setInvestigationId(newInv.id);
            });
        }
      });
  }, []);

  // Fetch transforms
  useEffect(() => {
    fetch("http://127.0.0.1:8080/api/transforms")
      .then((res) => res.json())
      .then((data) => setTransforms(data))
      .catch(console.error);
  }, []);

  // Initialize Cytoscape
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
            "text-valign": "bottom",
            "text-margin-y": 6,
            width: 38,
            height: 38,
          },
        },
        {
          selector: "node:selected",
          style: {
            "border-color": "#10b981",
            "border-width": 4,
            "background-color": "#0f766e",
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
          },
        },
      ],
      layout: { name: "cose", animate: false },
    });

    cyInstance.current.on("select", "node", (evt) => {
      const nodeData = evt.target.data("entity");
      setSelectedEntity(nodeData);
    });

    cyInstance.current.on("unselect", "node", () => {
      setSelectedEntity(null);
    });

    return () => {
      if (cyInstance.current) {
        cyInstance.current.destroy();
      }
    };
  }, []);

  // Load Graph for active investigation
  const loadGraph = (invId: string) => {
    if (!invId || !cyInstance.current) return;
    fetch(`http://127.0.0.1:8080/api/investigations/${invId}/graph`)
      .then((res) => res.json())
      .then((data) => {
        const cy = cyInstance.current!;
        cy.elements().remove();

        // Add nodes
        data.nodes.forEach((n: Entity) => {
          cy.add({
            group: "nodes",
            data: { id: n.id, label: n.label, entity: n },
          });
        });

        // Add edges
        data.edges.forEach((e: Relationship) => {
          cy.add({
            group: "edges",
            data: { id: e.id, source: e.source_id, target: e.target_id, label: e.type },
          });
        });

        cy.layout({ name: "cose", animate: true }).run();
      });
  };

  useEffect(() => {
    if (investigationId) {
      loadGraph(investigationId);
    }
  }, [investigationId]);

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
            data: { id: newEntity.id, label: newEntity.label, entity: newEntity },
          });
          cy.layout({ name: "cose", animate: true }).run();
        }
      });
  };

  // Run Transform
  const handleRunTransform = (tId: string) => {
    if (!selectedEntity || !investigationId) return;
    setIsRunningTransform(true);
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

  return (
    <>
      <header className="app-header">
        <div className="brand-badge">
          <Compass className="brand-icon" size={22} />
          <span>ARKANA INVESTIGATOR</span>
        </div>
        <div className="top-actions">
          <Database size={16} color="#94a3b8" />
          <select
            style={{
              background: "#1e293b",
              color: "#f1f5f9",
              border: "1px solid #2a3749",
              padding: "4px 8px",
              borderRadius: "4px",
            }}
            value={investigationId}
            onChange={(e) => setInvestigationId(e.target.value)}
          >
            {investigations.map((inv) => (
              <option key={inv.id} value={inv.id}>
                {inv.title}
              </option>
            ))}
          </select>
        </div>
      </header>

      <div className="workbench-body">
        {/* Left Palette */}
        <aside className="nav-sidebar">
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
              <button className="palette-btn" onClick={() => handleAddEntity("url", "https://target.com/api")}>
                <LinkIcon size={14} color="#8b5cf6" /> URL
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
            <button className="tool-btn" onClick={() => cyInstance.current?.layout({ name: "cose", animate: true }).run()}>
              Relayout
            </button>
          </div>

          <div id="cy-container" ref={cyRef} />

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
          <div className="inspector-header">Entity Inspector</div>
          {selectedEntity ? (
            <div className="inspector-content">
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
            </div>
          ) : (
            <div style={{ padding: "14px", fontSize: "12px", color: "#64748b" }}>
              Click on an entity in the graph to view properties and provenance.
            </div>
          )}
        </aside>
      </div>
    </>
  );
};

export default App;
