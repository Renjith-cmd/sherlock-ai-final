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
  Download,
  UploadCloud,
  RefreshCw,
  Eye,
  Sparkles,
  Split,
  LogOut,
  Shield,
  Lock,
  UserPlus,
  Bookmark
} from "lucide-react";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8080").replace(/\/$/, "");
const apiUrl = (url: string) => url.replace("http://127.0.0.1:8080", API_BASE_URL);

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
  properties?: Record<string, any>;
  provenance?: { source?: string; method?: string; confidence?: number; details?: Record<string, any> };
}

interface GraphConnection {
  id: string;
  type: string;
  sourceLabel: string;
  targetLabel: string;
  properties: Record<string, any>;
  provenance: { source?: string; method?: string; confidence?: number; details?: Record<string, any> };
}

interface GraphMatch {
  entity_a: { id: string; label: string; type: string };
  entity_b: { id: string; label: string; type: string };
  score: number;
  suggestion: string;
  evidence: string;
}

interface InputDialogState {
  title: string;
  initialValue: string;
  placeholder: string;
  secondaryPlaceholder?: string;
  submitLabel: string;
  onSubmit: (value: string) => Promise<void>;
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
  // ─── Authentication State ───────────────────────────────────────────
  const [authToken, setAuthToken] = useState<string | null>(() => localStorage.getItem("sherlock_ai_token"));
  const [currentUser, setCurrentUser] = useState<{ id: string; username: string; email: string; full_name: string } | null>(null);
  const [authView, setAuthView] = useState<"login" | "register">("login");
  const [authLoading, setAuthLoading] = useState(false);
  const [authError, setAuthError] = useState("");
  const [authForm, setAuthForm] = useState({ username: "", email: "", password: "", full_name: "" });

  // Authenticated fetch wrapper — adds Bearer token to every request
  const authFetch = (url: string, options: RequestInit = {}): Promise<Response> => {
    const headers: Record<string, string> = { ...(options.headers as Record<string, string> || {}) };
    if (authToken) {
      headers["Authorization"] = `Bearer ${authToken}`;
    }
    return fetch(apiUrl(url), { ...options, headers });
  };

  // Verify token on mount
  useEffect(() => {
    if (!authToken) return;
    fetch(apiUrl("http://127.0.0.1:8080/api/auth/me"), {
      headers: { Authorization: `Bearer ${authToken}` },
    })
      .then((r) => {
        if (!r.ok) throw new Error("Invalid session");
        return r.json();
      })
      .then((user) => setCurrentUser(user))
      .catch(() => {
        localStorage.removeItem("sherlock_ai_token");
        setAuthToken(null);
        setCurrentUser(null);
      });
  }, [authToken]);

  const formatAuthError = (errData: any, fallback: string): string => {
    if (!errData) return fallback;
    if (typeof errData === "string") return errData;
    if (typeof errData.detail === "string") return errData.detail;
    if (Array.isArray(errData.detail)) {
      return errData.detail.map((d: any) => d.msg || JSON.stringify(d)).join(", ");
    }
    if (typeof errData.message === "string") return errData.message;
    return fallback;
  };

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    setAuthLoading(true);
    setAuthError("");
    fetch(apiUrl("http://127.0.0.1:8080/api/auth/login"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ identifier: authForm.username, password: authForm.password }),
    })
      .then((r) => {
        if (!r.ok) return r.json().then((d) => { throw new Error(formatAuthError(d, "Login failed")); });
        return r.json();
      })
      .then((data) => {
        const token = data.token || data.access_token;
        localStorage.setItem("sherlock_ai_token", token);
        setAuthToken(token);
        if (data.user) {
          setCurrentUser(data.user);
        }
        setAuthLoading(false);
      })
      .catch((err) => {
        setAuthError(err.message);
        setAuthLoading(false);
      });
  };

  const handleRegister = (e: React.FormEvent) => {
    e.preventDefault();
    setAuthLoading(true);
    setAuthError("");
    fetch(apiUrl("http://127.0.0.1:8080/api/auth/register"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: authForm.username,
        email: authForm.email,
        password: authForm.password,
        full_name: authForm.full_name,
      }),
    })
      .then((r) => {
        if (!r.ok) return r.json().then((d) => { throw new Error(formatAuthError(d, "Registration failed")); });
        return r.json();
      })
      .then((data) => {
        const token = data.token || data.access_token;
        localStorage.setItem("sherlock_ai_token", token);
        setAuthToken(token);
        if (data.user) {
          setCurrentUser(data.user);
        }
        setAuthLoading(false);
      })
      .catch((err) => {
        setAuthError(err.message);
        setAuthLoading(false);
      });
  };

  const handleLogout = () => {
    localStorage.removeItem("sherlock_ai_token");
    setAuthToken(null);
    setCurrentUser(null);
    setAuthForm({ username: "", email: "", password: "", full_name: "" });
  };

  // ─── App State ──────────────────────────────────────────────────────
  const [investigationId, setInvestigationId] = useState<string>("");
  const [investigations, setInvestigations] = useState<Investigation[]>([]);
  const [showCaseModal, setShowCaseModal] = useState(false);
  const [inputDialog, setInputDialog] = useState<InputDialogState | null>(null);
  const [inputDialogValue, setInputDialogValue] = useState("");
  const [inputDialogError, setInputDialogError] = useState("");
  const [inputDialogBusy, setInputDialogBusy] = useState(false);
  const [inputDialogSecondary, setInputDialogSecondary] = useState("");
  const [showReportDialog, setShowReportDialog] = useState(false);
  const [reportBusy, setReportBusy] = useState(false);
  const [selectedEntity, setSelectedEntity] = useState<Entity | null>(null);
  const [graphMatches, setGraphMatches] = useState<GraphMatch[]>([]);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const [selectedConnection, setSelectedConnection] = useState<GraphConnection | null>(null);
  const [showAllConnections, setShowAllConnections] = useState(false);
  const [selectedNodeCount, setSelectedNodeCount] = useState<number>(0);
  const [transforms, setTransforms] = useState<TransformMeta[]>([]);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [isRunningTransform, setIsRunningTransform] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [currentLayout, setCurrentLayout] = useState<string>("cose");
  const [showAnalyticsModal, setShowAnalyticsModal] = useState(false);
  const [analyticsData, setAnalyticsData] = useState<any>(null);

  // Document Intelligence & Entity Resolution State
  const [showDocModal, setShowDocModal] = useState(false);
  const [docTab, setDocTab] = useState<"documents" | "entities" | "matches" | "relationships">("documents");
  const [documents, setDocuments] = useState<any[]>([]);
  const [isUploadingDoc, setIsUploadingDoc] = useState(false);
  const [documentUploadError, setDocumentUploadError] = useState("");
  const [selectedDocText, setSelectedDocText] = useState<{ filename: string; text: string } | null>(null);
  const [intelData, setIntelData] = useState<{
    canonical_entities: any[];
    match_candidates: any[];
    relationships: any[];
  }>({ canonical_entities: [], match_candidates: [], relationships: [] });
  const [selectedEntityIndices, setSelectedEntityIndices] = useState<number[]>([]);
  const [selectedRelIndices, setSelectedRelIndices] = useState<number[]>([]);
  const [includeDocNodeInGraph, setIncludeDocNodeInGraph] = useState(true);

  // Load documents & intelligence for current investigation
  const refreshDocumentsAndIntel = (invId: string) => {
    if (!invId) return;
    authFetch(`http://127.0.0.1:8080/api/investigations/${invId}/documents`)
      .then((r) => r.json())
      .then((data) => setDocuments(Array.isArray(data) ? data : []))
      .catch(console.error);

    authFetch(`http://127.0.0.1:8080/api/investigations/${invId}/intelligence`)
      .then((r) => r.json())
      .then((data) => {
        const canonical = Array.isArray(data.entities) ? data.entities : (Array.isArray(data.canonical_entities) ? data.canonical_entities : []);
        const rels = Array.isArray(data.relationships) ? data.relationships : [];
        const matches = Array.isArray(data.matches) ? data.matches : (Array.isArray(data.match_candidates) ? data.match_candidates : []);

        setIntelData({
          canonical_entities: canonical,
          relationships: rels,
          match_candidates: matches,
        });

        setSelectedEntityIndices(canonical.map((_: any, idx: number) => idx));
        setSelectedRelIndices(rels.map((_: any, idx: number) => idx));
      })
      .catch((err) => {
        console.error("Failed to load intelligence:", err);
        setIntelData({ canonical_entities: [], match_candidates: [], relationships: [] });
      });
  };

  useEffect(() => {
    if (investigationId) {
      refreshDocumentsAndIntel(investigationId);
    }
  }, [investigationId]);

  const handleFileUpload = (files: FileList | null) => {
    if (!files || files.length === 0 || !investigationId) return;
    setIsUploadingDoc(true);
    setDocumentUploadError("");

    const uploadPromises = Array.from(files).map((file) => {
      const formData = new FormData();
      formData.append("file", file);
      return authFetch(`http://127.0.0.1:8080/api/investigations/${investigationId}/documents/upload`, {
        method: "POST",
        body: formData,
      }).then(async (response) => {
        const result = await response.json();
        if (!response.ok) throw new Error(formatAuthError(result, `Could not process ${file.name}.`));
        return result;
      });
    });

    Promise.all(uploadPromises)
      .then((results) => {
        setIsUploadingDoc(false);
        refreshDocumentsAndIntel(investigationId);
        const hasMatches = results.some((result) => (result.cross_document_matches_count || 0) > 0);
        setDocTab(hasMatches ? "matches" : "entities");
      })
      .catch((err) => {
        console.error(err);
        setDocumentUploadError(err instanceof Error ? err.message : "Document upload failed.");
        setIsUploadingDoc(false);
      });
  };

  const handleReprocessDoc = (docId: string) => {
    if (!investigationId) return;
    authFetch(`http://127.0.0.1:8080/api/documents/${docId}/reprocess`, { method: "POST" })
      .then((r) => r.json())
      .then(() => {
        refreshDocumentsAndIntel(investigationId);
      });
  };

  const handleDeleteDoc = (docId: string) => {
    if (!investigationId || !window.confirm("Delete this document and all associated extractions?")) return;
    authFetch(`http://127.0.0.1:8080/api/documents/${docId}`, { method: "DELETE" })
      .then((r) => r.json())
      .then(() => {
        refreshDocumentsAndIntel(investigationId);
      });
  };

  const handleBuildGraphFromIntelligence = () => {
    if (!investigationId) return;
    const chosenEntities = selectedEntityIndices.map((idx) => intelData.canonical_entities[idx]);
    const chosenRels = selectedRelIndices.map((idx) => intelData.relationships[idx]);

    authFetch(`http://127.0.0.1:8080/api/investigations/${investigationId}/intelligence/build-graph`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        selected_entities: chosenEntities,
        selected_relationships: chosenRels,
        include_document_node: includeDocNodeInGraph,
        document_id: documents.length > 0 ? documents[0].id : undefined,
      }),
    })
      .then((r) => r.json())
      .then((res) => {
        loadGraph(investigationId);
        setShowDocModal(false);
        alert(`Graph populated with ${res.created_nodes_count} entities and ${res.created_edges_count} relationships!`);
      })
      .catch(console.error);
  };

  const fetchAnalytics = () => {
    if (!investigationId) return;
    authFetch(`http://127.0.0.1:8080/api/investigations/${investigationId}/analytics`)
      .then((r) => r.json())
      .then((data) => {
        setAnalyticsData(data);
        setShowAnalyticsModal(true);
      });
  };

  const downloadInvestigationReport = async () => {
    if (!investigationId) return;
    setReportBusy(true);
    try {
      const response = await authFetch(`http://127.0.0.1:8080/api/investigations/${investigationId}/report/pdf`);
      if (!response.ok) {
        const error = await response.json().catch(() => null);
        throw new Error(formatAuthError(error, "Could not generate the PDF report."));
      }
      const reportBlob = await response.blob();
      const downloadUrl = URL.createObjectURL(reportBlob);
      const link = document.createElement("a");
      const caseTitle = investigations.find((item) => item.id === investigationId)?.title || "sherlock-ai-report";
      link.href = downloadUrl;
      link.download = `${caseTitle}.pdf`.replace(/[^a-z0-9._-]+/gi, "-");
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(downloadUrl);
      setShowReportDialog(false);
    } catch (error) {
      setInputDialogError(error instanceof Error ? error.message : "Could not download report.");
    } finally {
      setReportBusy(false);
    }
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
  const layoutInstance = useRef<ReturnType<Core["layout"]> | null>(null);

  const resetCaseView = (nextInvestigationId: string) => {
    setDocuments([]);
    setIntelData({ canonical_entities: [], match_candidates: [], relationships: [] });
    setSelectedEntityIndices([]);
    setSelectedRelIndices([]);
    setSelectedDocText(null);
    setGraphMatches([]);
    setSelectedEntity(null);
    setSelectedEdgeId(null);
    cyInstance.current?.elements().remove();
    setInvestigationId(nextInvestigationId);
  };

  // Load investigations list
  const refreshInvestigations = (selectId?: string) => {
    if (!authToken) return;
    authFetch("http://127.0.0.1:8080/api/investigations")
      .then((res) => res.json())
      .then((data) => {
        const list = Array.isArray(data) ? data : [];
        setInvestigations(list);
        if (selectId) {
          resetCaseView(selectId);
        } else if (list.length > 0 && !investigationId) {
          resetCaseView(list[0].id);
        }
      })
      .catch((err) => console.error("Error loading investigations:", err));
  };

  useEffect(() => {
    if (authToken && currentUser) {
      refreshInvestigations();
    }
  }, [authToken, currentUser]);

  // Fetch transforms
  useEffect(() => {
    if (authToken && currentUser) {
      authFetch("http://127.0.0.1:8080/api/transforms")
        .then((res) => res.json())
        .then((data) => setTransforms(Array.isArray(data) ? data : []))
        .catch(console.error);
    }
  }, [authToken, currentUser]);

  // Cytoscape initialization
  useEffect(() => {
    if (!authToken || !currentUser) return;
    if (!cyRef.current) return;

    cyInstance.current = cytoscape({
      container: cyRef.current,
      minZoom: 0.25,
      maxZoom: 3.0,
      wheelSensitivity: 0.2,
      boxSelectionEnabled: true,
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
            "text-margin-y": 8,
            "text-wrap": "wrap",
            "text-max-width": "120px",
            "text-overflow-wrap": "anywhere",
            "text-outline-color": "#07111f",
            "text-outline-width": 2,
            "text-outline-opacity": 1,
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
          selector: "node[type = 'document']",
          style: { "border-color": "#06b6d4", "background-color": "#164e63" },
        },
        {
          selector: "node[type = 'url']",
          style: { "border-color": "#8b5cf6", "background-color": "#4c1d95" },
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
            label: "",
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
            label: "data(label)",
            width: 4,
            "line-color": "#38bdf8",
            "target-arrow-color": "#38bdf8",
            color: "#38bdf8",
          },
        },
        {
          selector: "edge.match-edge",
          style: {
            display: "none",
            width: 2,
            "line-color": "#f59e0b",
            "line-style": "dashed",
            "target-arrow-shape": "none",
            label: "data(label)",
            color: "#fbbf24",
            "font-size": "10px",
            "font-weight": 700,
            "text-background-opacity": 0.95,
            "text-background-color": "#17130a",
            "text-background-padding": "3px",
            "curve-style": "unbundled-bezier",
            "control-point-distances": 54,
            "control-point-weights": 0.5,
            events: "no",
          },
        },
        {
          selector: "edge.match-edge.match-visible",
          style: { display: "element" },
        },
        {
          selector: "edge.low-signal-hidden",
          style: { display: "none" },
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
        cy.edges(".match-edge").removeClass("match-visible");
        cy.edges(".match-edge").filter((edge) =>
          edge.data("source") === evt.target.id() || edge.data("target") === evt.target.id()
        ).addClass("match-visible");
      } else {
        setSelectedEntity(null);
        cy.edges(".match-edge").removeClass("match-visible");
      }
      setSelectedEdgeId(null);
      setSelectedConnection(null);
    });

    cy.on("unselect", "node", () => {
      const selected = cy.$("node:selected");
      setSelectedNodeCount(selected.length);
      if (selected.length === 1) {
        setSelectedEntity(selected[0].data("entity"));
      } else {
        setSelectedEntity(null);
        cy.edges(".match-edge").removeClass("match-visible");
      }
    });

    cy.on("select", "edge", (evt: EventObject) => {
      const edge = evt.target;
      setSelectedEdgeId(edge.id());
      setSelectedConnection({
        id: edge.id(),
        type: edge.data("label") || edge.data("type") || "ASSOCIATED_WITH",
        sourceLabel: edge.data("source_label") || edge.data("sourceLabel") || edge.source().data("label") || "Unknown entity",
        targetLabel: edge.data("target_label") || edge.data("targetLabel") || edge.target().data("label") || "Unknown entity",
        properties: edge.data("properties") || {},
        provenance: edge.data("provenance") || {},
      });
      setSelectedEntity(null);
    });

    cy.on("unselect", "edge", () => {
      setSelectedEdgeId(null);
      setSelectedConnection(null);
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

    if (investigationId) {
      loadGraph(investigationId);
    }

    return () => {
      if (cyInstance.current) {
        layoutInstance.current?.stop();
        layoutInstance.current = null;
        cyInstance.current.stop(true);
        cyInstance.current.destroy();
        cyInstance.current = null;
      }
    };
  }, [authToken, currentUser]);

  // Load Graph elements
  const loadGraph = (invId: string, layoutName: string = currentLayout) => {
    if (!invId || !cyInstance.current) return;
    authFetch(`http://127.0.0.1:8080/api/investigations/${invId}/graph`)
      .then((res) => res.json())
      .then((data) => {
        if (!cyInstance.current) return;
        const cy = cyInstance.current;
        cy.elements().remove();

        const nodes = Array.isArray(data?.nodes) ? data.nodes : [];
        const edges = Array.isArray(data?.edges) ? data.edges : [];
        const matches: GraphMatch[] = Array.isArray(data?.matches) ? data.matches : [];
        setGraphMatches(matches);

        nodes.forEach((n: Entity) => {
          cy.add({
            group: "nodes",
            data: { id: n.id, label: n.label, type: n.type, entity: n },
          });
        });

        edges.forEach((e: Relationship) => {
          cy.add({
            group: "edges",
            data: {
              id: e.id,
              source: (e as any).source ?? e.source_id,
              target: (e as any).target ?? e.target_id,
              label: (e as any).label ?? e.type,
              source_label: (e as any).source_label,
              target_label: (e as any).target_label,
              properties: e.properties || (e as any).properties || {},
              provenance: e.provenance || (e as any).provenance || {},
            },
            classes: (() => {
              const provenance = e.provenance || (e as any).provenance || {};
              const confidence = Number(provenance.confidence ?? 1);
              const relationshipType = String(e.type || (e as any).label || "").toUpperCase();
              const lowSignal = relationshipType === "MENTIONS" || provenance.method === "co_occurrence_extraction" || confidence < 0.7;
              return lowSignal ? `low-signal-edge${showAllConnections ? "" : " low-signal-hidden"}` : "";
            })(),
          });
        });

        matches.forEach((match) => {
          const source = match.entity_a?.id;
          const target = match.entity_b?.id;
          if (!source || !target) return;
          cy.add({
            group: "edges",
            classes: "match-edge",
            data: {
              id: `match-${[source, target].sort().join("-")}`,
              source,
              target,
              label: `POSSIBLE MATCH ${Math.round(match.score * 100)}%`,
            },
          });
        });

        if (nodes.length > 0) {
          applyLayout(layoutName);
        }
      })
      .catch((err) => console.error("Error loading graph:", err));
  };

  const handleConfirmGraphMatch = (match: GraphMatch) => {
    if (!investigationId) return;
    authFetch(`http://127.0.0.1:8080/api/investigations/${investigationId}/relationships`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source_id: match.entity_a.id,
        target_id: match.entity_b.id,
        type: "MATCHES",
        properties: { match_score: match.score, suggestion: match.suggestion },
        provenance: {
          source: "analyst_review",
          method: "entity_resolution_confirmation",
          confidence: match.score,
          details: { evidence: match.evidence },
        },
      }),
    })
      .then((response) => {
        if (!response.ok) throw new Error("Could not confirm entity match.");
        return response.json();
      })
      .then(() => loadGraph(investigationId))
      .catch(console.error);
  };

  const applyLayout = (name: string) => {
    if (!cyInstance.current) return;
    setCurrentLayout(name);
    const cy = cyInstance.current;
    layoutInstance.current?.stop();

    const totalNodes = cy.nodes().length;
    if (totalNodes === 0) return;

    // For single or 2 nodes, center comfortably without extreme zoom
    if (totalNodes <= 2) {
      const singleLayout = cy.layout({
        name: "grid",
        rows: 1,
        cols: Math.max(totalNodes, 1),
        avoidOverlap: true,
        padding: 100,
        fit: false,
      });
      layoutInstance.current = singleLayout;
      singleLayout.run();
      cy.center();
      cy.zoom(1.0);
      return;
    }

    let layoutOpts: any = {
      name,
      animate: true,
      animationDuration: 400,
      fit: true,
      padding: 60,
    };

    if (name === "cose") {
      layoutOpts = {
        ...layoutOpts,
        nodeRepulsion: () => 45000,
        nodeOverlap: 60,
        idealEdgeLength: () => 140,
        edgeElasticity: () => 100,
        nestingFactor: 5,
        gravity: 0.15,
        numIter: 1000,
        initialTemp: 300,
        coolingFactor: 0.95,
        minTemp: 1.0,
      };
    } else if (name === "concentric") {
      layoutOpts = {
        ...layoutOpts,
        minNodeSpacing: 100,
        concentric: (node: any) => node.degree(),
        levelWidth: () => 2,
      };
    } else if (name === "breadthfirst") {
      layoutOpts = {
        ...layoutOpts,
        directed: false,
        spacingFactor: 2.0,
      };
    } else if (name === "circle") {
      layoutOpts = {
        ...layoutOpts,
        spacingFactor: 1.8,
      };
    } else if (name === "grid") {
      layoutOpts = {
        ...layoutOpts,
        spacingFactor: 2.0,
        avoidOverlap: true,
      };
    }

    const layout = cy.layout(layoutOpts);
    layoutInstance.current = layout;
    layout.one("layoutstop", () => {
      if (cyInstance.current !== cy || cy.destroyed()) return;
      if (layoutInstance.current === layout) layoutInstance.current = null;
      // Clamp zoom to comfortable viewing range: between 0.65 and 1.3
      const currentZ = cy.zoom();
      if (currentZ > 1.3) {
        cy.zoom(1.1);
        cy.center();
      }
    });
    layout.run();
  };

  useEffect(() => {
    if (investigationId) {
      loadGraph(investigationId);
    }
  }, [investigationId]);

  useEffect(() => {
    const cy = cyInstance.current;
    if (!cy) return;
    cy.edges(".low-signal-edge").forEach((edge) => {
      edge.toggleClass("low-signal-hidden", !showAllConnections);
    });
  }, [showAllConnections]);

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
    if (!investigationId) return;
    setInputDialogError("");
    setInputDialogValue(defaultLabel);
    setInputDialog({
      title: `Add ${type} entity`,
      initialValue: defaultLabel,
      placeholder: `Enter ${type} value`,
      submitLabel: "Add entity",
      onSubmit: async (label) => {
        const response = await authFetch(`http://127.0.0.1:8080/api/investigations/${investigationId}/entities`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ type, label, properties: {} }),
        });
        const result = await response.json();
        if (!response.ok) throw new Error(formatAuthError(result, "Could not add entity."));
        loadGraph(investigationId);
        setInputDialog(null);
      },
    });
  };

  // Investigation Management Actions
  const handleCreateInvestigation = () => {
    setInputDialogError("");
    setInputDialogValue("");
    setInputDialog({
      title: "Create new case",
      initialValue: "",
      placeholder: "Case name",
      submitLabel: "Create case",
      onSubmit: async (title) => {
        const response = await authFetch("http://127.0.0.1:8080/api/investigations", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ title, description: "Active Sherlock AI workspace" }),
        });
        const result = await response.json();
        if (!response.ok) throw new Error(formatAuthError(result, "Could not create case."));
        resetCaseView(result.id);
        setInvestigations((current) => [result, ...current]);
        setShowCaseModal(false);
        setInputDialog(null);
      },
    });
  };

  const handleDuplicateInvestigation = (idToDup: string) => {
    const target = investigations.find((i) => i.id === idToDup);
    setInputDialogError("");
    setInputDialogValue(target ? `${target.title} (Clone)` : "Investigation Copy");
    setInputDialog({
      title: "Duplicate case",
      initialValue: target ? `${target.title} (Clone)` : "Investigation Copy",
      placeholder: "Case name",
      submitLabel: "Duplicate case",
      onSubmit: async (title) => {
        const response = await authFetch(`http://127.0.0.1:8080/api/investigations/${idToDup}/duplicate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ title }),
        });
        const result = await response.json();
        if (!response.ok) throw new Error(formatAuthError(result, "Could not duplicate case."));
        refreshInvestigations(result.id);
        setShowCaseModal(false);
        setInputDialog(null);
      },
    });
  };

  const handleDeleteInvestigation = (idToDel: string) => {
    if (!window.confirm("Are you sure you want to permanently delete this investigation and its entire graph?")) return;
    authFetch(`http://127.0.0.1:8080/api/investigations/${idToDel}`, { method: "DELETE" })
      .then((r) => r.json())
      .then(() => {
        const remaining = investigations.filter((i) => i.id !== idToDel);
        setInvestigations(remaining);
        resetCaseView(remaining[0]?.id || "");
      });
  };

  // Delete Entity
  const handleDeleteEntity = (entityId: string) => {
    if (!window.confirm("Are you sure you want to delete this entity from the investigation?")) return;
    authFetch(`http://127.0.0.1:8080/api/entities/${entityId}`, { method: "DELETE" })
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
    authFetch(`http://127.0.0.1:8080/api/relationships/${edgeId}`, { method: "DELETE" })
      .then((res) => res.json())
      .then(() => {
        cyInstance.current?.$(`#${edgeId}`).remove();
        setSelectedEdgeId(null);
      });
  };

  // Rename Entity
  const handleRenameEntity = (entity: Entity) => {
    setInputDialogError("");
    setInputDialogValue(entity.label);
    setInputDialog({
      title: "Rename entity",
      initialValue: entity.label,
      placeholder: "Entity label",
      submitLabel: "Save name",
      onSubmit: async (newLabel) => {
        const response = await authFetch(`http://127.0.0.1:8080/api/entities/${entity.id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ label: newLabel }),
        });
        const updated = await response.json();
        if (!response.ok) throw new Error(formatAuthError(updated, "Could not rename entity."));
        const node = cyInstance.current?.$(`#${entity.id}`);
        if (node) {
          node.data("label", updated.label);
          node.data("entity", updated);
        }
        setSelectedEntity(updated);
        setContextMenu(null);
        setInputDialog(null);
      },
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

    setInputDialogValue("CONNECTED_TO");
    setInputDialogError("");
    setInputDialog({
      title: "Create relationship",
      initialValue: "CONNECTED_TO",
      placeholder: "Relationship label",
      submitLabel: "Connect entities",
      onSubmit: async (relType) => {
        const response = await authFetch(`http://127.0.0.1:8080/api/investigations/${investigationId}/relationships`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ source_id: linkSourceNodeId, target_id: targetId, type: relType }),
        });
        const rel = await response.json();
        if (!response.ok) throw new Error(formatAuthError(rel, "Could not connect entities."));
        cyInstance.current?.add({
          group: "edges",
          data: { id: rel.id, source: rel.source_id, target: rel.target_id, label: rel.type },
        });
        setLinkSourceNodeId(null);
        setInputDialog(null);
      },
    });
  };

  // Run Transform
  const handleRunTransform = (tId: string) => {
    if (!selectedEntity || !investigationId) return;
    setIsRunningTransform(true);
    setContextMenu(null);
    authFetch(`http://127.0.0.1:8080/api/investigations/${investigationId}/transforms/execute`, {
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
    authFetch(`http://127.0.0.1:8080/api/investigations/${investigationId}/transforms/merge`, {
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

  const activeInv = Array.isArray(investigations) ? investigations.find((i) => i.id === investigationId) : undefined;
  const selectedGraphMatches = selectedEntity
    ? graphMatches.filter((match) => match.entity_a.id === selectedEntity.id || match.entity_b.id === selectedEntity.id)
    : [];

  // ─── AUTH GATE: Show Login/Register if not authenticated ────────────
  if (!authToken || !currentUser) {
    return (
      <div style={{
        minHeight: "100vh",
        width: "100vw",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "linear-gradient(135deg, #0a0f1a 0%, #0f172a 30%, #1a1040 70%, #0f172a 100%)",
        fontFamily: "var(--font-family)",
        position: "relative",
        overflow: "hidden",
      }}>
        {/* Animated background grid */}
        <div style={{
          position: "absolute", inset: 0,
          backgroundImage: "radial-gradient(circle at 1px 1px, rgba(59,130,246,0.08) 1px, transparent 0)",
          backgroundSize: "32px 32px",
          animation: "pulse 4s ease-in-out infinite",
        }} />

        {/* Glow orbs */}
        <div style={{
          position: "absolute", top: "15%", left: "20%", width: 320, height: 320,
          borderRadius: "50%", background: "radial-gradient(circle, rgba(59,130,246,0.12), transparent 70%)",
          filter: "blur(60px)", pointerEvents: "none",
        }} />
        <div style={{
          position: "absolute", bottom: "15%", right: "15%", width: 280, height: 280,
          borderRadius: "50%", background: "radial-gradient(circle, rgba(139,92,246,0.1), transparent 70%)",
          filter: "blur(60px)", pointerEvents: "none",
        }} />

        <div style={{
          position: "relative", zIndex: 1,
          width: 420,
          background: "rgba(22,31,45,0.85)",
          backdropFilter: "blur(24px)",
          border: "1px solid rgba(59,130,246,0.2)",
          borderRadius: 16,
          padding: "40px 36px",
          boxShadow: "0 24px 64px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.05)",
        }}>
          {/* Logo & Title */}
          <div style={{ textAlign: "center", marginBottom: 32 }}>
            <div style={{
              width: 56, height: 56, borderRadius: "50%",
              background: "linear-gradient(135deg, #3b82f6, #8b5cf6)",
              display: "flex", alignItems: "center", justifyContent: "center",
              margin: "0 auto 16px",
              boxShadow: "0 8px 24px rgba(59,130,246,0.3)",
            }}>
              <Shield size={28} color="#fff" />
            </div>
            <h1 style={{ fontSize: 22, fontWeight: 700, color: "#f1f5f9", margin: 0, letterSpacing: "0.5px" }}>
              SHERLOCK AI
            </h1>
            <p style={{ fontSize: 13, color: "#64748b", marginTop: 6 }}>
              Intelligence-grade investigation platform
            </p>
          </div>

          {/* Tab Switcher */}
          <div style={{ display: "flex", marginBottom: 24, background: "#0f172a", borderRadius: 8, padding: 3 }}>
            <button
              onClick={() => { setAuthView("login"); setAuthError(""); }}
              style={{
                flex: 1, padding: "10px 0", border: "none", borderRadius: 6, cursor: "pointer",
                fontSize: 13, fontWeight: 600, transition: "all 0.2s",
                background: authView === "login" ? "linear-gradient(135deg, #3b82f6, #2563eb)" : "transparent",
                color: authView === "login" ? "#fff" : "#64748b",
              }}
            >
              <Lock size={14} style={{ marginRight: 6, verticalAlign: "middle" }} />
              Sign In
            </button>
            <button
              onClick={() => { setAuthView("register"); setAuthError(""); }}
              style={{
                flex: 1, padding: "10px 0", border: "none", borderRadius: 6, cursor: "pointer",
                fontSize: 13, fontWeight: 600, transition: "all 0.2s",
                background: authView === "register" ? "linear-gradient(135deg, #8b5cf6, #6d28d9)" : "transparent",
                color: authView === "register" ? "#fff" : "#64748b",
              }}
            >
              <UserPlus size={14} style={{ marginRight: 6, verticalAlign: "middle" }} />
              Register
            </button>
          </div>

          {/* Error Alert */}
          {authError && (
            <div style={{
              background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)",
              borderRadius: 8, padding: "10px 14px", marginBottom: 16,
              color: "#fca5a5", fontSize: 13, display: "flex", alignItems: "center", gap: 8,
            }}>
              <XCircle size={16} /> {authError}
            </div>
          )}

          {/* Login Form */}
          {authView === "login" ? (
            <form onSubmit={handleLogin} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <div>
                <label style={{ fontSize: 11, fontWeight: 600, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.5px", display: "block", marginBottom: 6 }}>
                  Username
                </label>
                <input
                  type="text"
                  required
                  autoComplete="username"
                  value={authForm.username}
                  onChange={(e) => setAuthForm({ ...authForm, username: e.target.value })}
                  placeholder="analyst_username"
                  style={{
                    width: "100%", padding: "12px 14px", background: "#0f172a",
                    border: "1px solid #2a3749", borderRadius: 8, color: "#f1f5f9",
                    fontSize: 14, outline: "none", transition: "border-color 0.2s",
                    boxSizing: "border-box",
                  }}
                  onFocus={(e) => e.target.style.borderColor = "#3b82f6"}
                  onBlur={(e) => e.target.style.borderColor = "#2a3749"}
                />
              </div>
              <div>
                <label style={{ fontSize: 11, fontWeight: 600, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.5px", display: "block", marginBottom: 6 }}>
                  Password
                </label>
                <input
                  type="password"
                  required
                  autoComplete="current-password"
                  value={authForm.password}
                  onChange={(e) => setAuthForm({ ...authForm, password: e.target.value })}
                  placeholder="••••••••••"
                  style={{
                    width: "100%", padding: "12px 14px", background: "#0f172a",
                    border: "1px solid #2a3749", borderRadius: 8, color: "#f1f5f9",
                    fontSize: 14, outline: "none", transition: "border-color 0.2s",
                    boxSizing: "border-box",
                  }}
                  onFocus={(e) => e.target.style.borderColor = "#3b82f6"}
                  onBlur={(e) => e.target.style.borderColor = "#2a3749"}
                />
              </div>
              <button
                type="submit"
                disabled={authLoading}
                style={{
                  padding: "14px", border: "none", borderRadius: 8, cursor: "pointer",
                  fontSize: 14, fontWeight: 700, color: "#fff", marginTop: 8,
                  background: authLoading ? "#374151" : "linear-gradient(135deg, #3b82f6, #2563eb)",
                  boxShadow: authLoading ? "none" : "0 4px 16px rgba(59,130,246,0.3)",
                  transition: "all 0.2s", letterSpacing: "0.3px",
                }}
              >
                {authLoading ? "Authenticating..." : "Sign In to Workspace"}
              </button>
            </form>
          ) : (
            /* Register Form */
            <form onSubmit={handleRegister} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <div>
                <label style={{ fontSize: 11, fontWeight: 600, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.5px", display: "block", marginBottom: 6 }}>
                  Full Name
                </label>
                <input
                  type="text"
                  required
                  value={authForm.full_name}
                  onChange={(e) => setAuthForm({ ...authForm, full_name: e.target.value })}
                  placeholder="Senior Intelligence Analyst"
                  style={{
                    width: "100%", padding: "11px 14px", background: "#0f172a",
                    border: "1px solid #2a3749", borderRadius: 8, color: "#f1f5f9",
                    fontSize: 13, outline: "none", transition: "border-color 0.2s",
                    boxSizing: "border-box",
                  }}
                  onFocus={(e) => e.target.style.borderColor = "#8b5cf6"}
                  onBlur={(e) => e.target.style.borderColor = "#2a3749"}
                />
              </div>
              <div>
                <label style={{ fontSize: 11, fontWeight: 600, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.5px", display: "block", marginBottom: 6 }}>
                  Username
                </label>
                <input
                  type="text"
                  required
                  autoComplete="username"
                  value={authForm.username}
                  onChange={(e) => setAuthForm({ ...authForm, username: e.target.value })}
                  placeholder="analyst_call_sign"
                  style={{
                    width: "100%", padding: "11px 14px", background: "#0f172a",
                    border: "1px solid #2a3749", borderRadius: 8, color: "#f1f5f9",
                    fontSize: 13, outline: "none", transition: "border-color 0.2s",
                    boxSizing: "border-box",
                  }}
                  onFocus={(e) => e.target.style.borderColor = "#8b5cf6"}
                  onBlur={(e) => e.target.style.borderColor = "#2a3749"}
                />
              </div>
              <div>
                <label style={{ fontSize: 11, fontWeight: 600, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.5px", display: "block", marginBottom: 6 }}>
                  Email
                </label>
                <input
                  type="email"
                  required
                  autoComplete="email"
                  value={authForm.email}
                  onChange={(e) => setAuthForm({ ...authForm, email: e.target.value })}
                  placeholder="analyst@agency.gov"
                  style={{
                    width: "100%", padding: "11px 14px", background: "#0f172a",
                    border: "1px solid #2a3749", borderRadius: 8, color: "#f1f5f9",
                    fontSize: 13, outline: "none", transition: "border-color 0.2s",
                    boxSizing: "border-box",
                  }}
                  onFocus={(e) => e.target.style.borderColor = "#8b5cf6"}
                  onBlur={(e) => e.target.style.borderColor = "#2a3749"}
                />
              </div>
              <div>
                <label style={{ fontSize: 11, fontWeight: 600, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.5px", display: "block", marginBottom: 6 }}>
                  Password
                </label>
                <input
                  type="password"
                  required
                  autoComplete="new-password"
                  minLength={8}
                  value={authForm.password}
                  onChange={(e) => setAuthForm({ ...authForm, password: e.target.value })}
                  placeholder="Min 8 characters, 1 uppercase, 1 digit"
                  style={{
                    width: "100%", padding: "11px 14px", background: "#0f172a",
                    border: "1px solid #2a3749", borderRadius: 8, color: "#f1f5f9",
                    fontSize: 13, outline: "none", transition: "border-color 0.2s",
                    boxSizing: "border-box",
                  }}
                  onFocus={(e) => e.target.style.borderColor = "#8b5cf6"}
                  onBlur={(e) => e.target.style.borderColor = "#2a3749"}
                />
              </div>
              <button
                type="submit"
                disabled={authLoading}
                style={{
                  padding: "13px", border: "none", borderRadius: 8, cursor: "pointer",
                  fontSize: 14, fontWeight: 700, color: "#fff", marginTop: 6,
                  background: authLoading ? "#374151" : "linear-gradient(135deg, #8b5cf6, #6d28d9)",
                  boxShadow: authLoading ? "none" : "0 4px 16px rgba(139,92,246,0.3)",
                  transition: "all 0.2s", letterSpacing: "0.3px",
                }}
              >
                {authLoading ? "Creating Account..." : "Create Analyst Account"}
              </button>
            </form>
          )}

          {/* Security Badge */}
          <div style={{
            marginTop: 24, textAlign: "center", fontSize: 11, color: "#475569",
            display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
          }}>
            <Lock size={10} /> Argon2id + JWT · End-to-end encrypted sessions
          </div>
        </div>
      </div>
    );
  }

  // ─── MAIN APP (Authenticated) ──────────────────────────────────────
  return (
    <>
      <header className="app-header">
        <div className="brand-badge">
          <Compass className="brand-icon" size={22} />
          <span>SHERLOCK AI</span>
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
                window.open(apiUrl(`http://127.0.0.1:8080/api/investigations/${investigationId}/export/json`), "_blank");
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
                setInputDialogError("");
                setShowReportDialog(true);
              }
            }}
          >
            <FileText size={13} color="#f59e0b" /> Report
          </button>

          <button
            className="tool-btn"
            style={{ background: "#1e293b", border: "1px solid #3b82f6", color: "#38bdf8" }}
            title="Document Intelligence & Entity Resolution"
            onClick={() => setShowDocModal(true)}
          >
            <UploadCloud size={13} color="#38bdf8" /> Documents ({documents.length})
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

          {/* User Badge & Logout */}
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginLeft: 8, paddingLeft: 12, borderLeft: "1px solid #2a3749" }}>
            <div style={{
              width: 28, height: 28, borderRadius: "50%",
              background: "linear-gradient(135deg, #3b82f6, #8b5cf6)",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 12, fontWeight: 700, color: "#fff",
            }}>
              {currentUser?.username?.charAt(0)?.toUpperCase() || "U"}
            </div>
            <span style={{ fontSize: 12, color: "#94a3b8", maxWidth: 100, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {currentUser?.username || "user"}
            </span>
            <button
              className="tool-btn"
              title="Sign Out"
              onClick={handleLogout}
              style={{ padding: "4px 8px", background: "rgba(239,68,68,0.15)", border: "1px solid rgba(239,68,68,0.3)", color: "#fca5a5" }}
            >
              <LogOut size={13} />
            </button>
          </div>
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
                          resetCaseView(inv.id);
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

      {/* Document Intelligence & Entity Resolution Modal */}
      {showDocModal && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: "rgba(0,0,0,0.8)",
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
              width: "900px",
              maxHeight: "85vh",
              display: "flex",
              flexDirection: "column",
              boxShadow: "0 16px 40px rgba(0,0,0,0.9)",
            }}
          >
            {/* Modal Header */}
            <div style={{ padding: "16px", borderBottom: "1px solid #2a3749", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <Sparkles size={18} color="#38bdf8" />
                <span style={{ fontWeight: 700, fontSize: "16px" }}>Document Intelligence & Entity Resolution</span>
              </div>
              <button
                onClick={() => setShowDocModal(false)}
                style={{ background: "transparent", border: "none", color: "#94a3b8", cursor: "pointer", fontSize: "16px" }}
              >
                ✕
              </button>
            </div>

            {/* Modal Navigation Tabs */}
            <div style={{ display: "flex", borderBottom: "1px solid #2a3749", background: "#0f141c", padding: "0 16px" }}>
              <button
                style={{
                  background: "transparent",
                  border: "none",
                  borderBottom: docTab === "documents" ? "2px solid #38bdf8" : "2px solid transparent",
                  color: docTab === "documents" ? "#38bdf8" : "#94a3b8",
                  padding: "10px 16px",
                  cursor: "pointer",
                  fontWeight: 600,
                  fontSize: "13px",
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                }}
                onClick={() => setDocTab("documents")}
              >
                <UploadCloud size={14} /> Documents ({documents.length})
              </button>
              <button
                style={{
                  background: "transparent",
                  border: "none",
                  borderBottom: docTab === "entities" ? "2px solid #38bdf8" : "2px solid transparent",
                  color: docTab === "entities" ? "#38bdf8" : "#94a3b8",
                  padding: "10px 16px",
                  cursor: "pointer",
                  fontWeight: 600,
                  fontSize: "13px",
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                }}
                onClick={() => setDocTab("entities")}
              >
                <User size={14} /> Extracted Entities ({intelData.canonical_entities?.length || 0})
              </button>
              <button
                style={{
                  background: "transparent",
                  border: "none",
                  borderBottom: docTab === "matches" ? "2px solid #38bdf8" : "2px solid transparent",
                  color: docTab === "matches" ? "#38bdf8" : "#94a3b8",
                  padding: "10px 16px",
                  cursor: "pointer",
                  fontWeight: 600,
                  fontSize: "13px",
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                }}
                onClick={() => setDocTab("matches")}
              >
                <Split size={14} /> Cross-Doc Matches ({intelData.match_candidates?.length || 0})
              </button>
              <button
                style={{
                  background: "transparent",
                  border: "none",
                  borderBottom: docTab === "relationships" ? "2px solid #38bdf8" : "2px solid transparent",
                  color: docTab === "relationships" ? "#38bdf8" : "#94a3b8",
                  padding: "10px 16px",
                  cursor: "pointer",
                  fontWeight: 600,
                  fontSize: "13px",
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                }}
                onClick={() => setDocTab("relationships")}
              >
                <LinkIcon size={14} /> Relationships ({intelData.relationships?.length || 0})
              </button>
            </div>

            {/* Modal Body */}
            <div style={{ padding: "16px", overflowY: "auto", flex: 1, maxHeight: "calc(85vh - 130px)" }}>
              {/* TAB 1: Documents Upload & Management */}
              {docTab === "documents" && (
                <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                  {documentUploadError && (
                    <div role="alert" style={{ padding: "10px 12px", border: "1px solid #7f1d1d", borderRadius: "5px", background: "#2b1115", color: "#fca5a5", fontSize: "12px" }}>
                      {documentUploadError}
                    </div>
                  )}
                  {/* Dropzone */}
                  <div
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={(e) => {
                      e.preventDefault();
                      handleFileUpload(e.dataTransfer.files);
                    }}
                    style={{
                      border: "2px dashed #3b82f6",
                      borderRadius: "8px",
                      padding: "24px",
                      textAlign: "center",
                      background: "rgba(59, 130, 246, 0.05)",
                      cursor: "pointer",
                    }}
                    onClick={() => {
                      const input = document.createElement("input");
                      input.type = "file";
                      input.multiple = true;
                      input.onchange = (e: any) => handleFileUpload(e.target.files);
                      input.click();
                    }}
                  >
                    <UploadCloud size={32} color="#38bdf8" style={{ margin: "0 auto 8px" }} />
                    <div style={{ fontWeight: 600, fontSize: "14px" }}>
                      {isUploadingDoc ? "Processing & Extracting Entities..." : "Click or Drag & Drop Documents Here"}
                    </div>
                    <div style={{ fontSize: "12px", color: "#94a3b8", marginTop: "4px" }}>
                      Supported formats: PDF, DOCX, TXT, MD, CSV, JSON (Up to 25MB)
                    </div>
                  </div>

                  {/* Documents List */}
                  <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                    <div style={{ fontSize: "12px", fontWeight: 700, color: "#94a3b8", textTransform: "uppercase" }}>
                      Uploaded Documents ({documents.length})
                    </div>
                    {documents.length === 0 ? (
                      <div style={{ fontSize: "13px", color: "#64748b", padding: "12px", textAlign: "center" }}>
                        No documents uploaded yet for this investigation.
                      </div>
                    ) : (
                      documents.map((d) => (
                        <div
                          key={d.id}
                          style={{
                            background: "#0f172a",
                            border: "1px solid #2a3749",
                            borderRadius: "6px",
                            padding: "10px 14px",
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center",
                          }}
                        >
                          <div>
                            <div style={{ fontWeight: 600, fontSize: "13px", color: "#f1f5f9" }}>
                              {d.filename}{" "}
                              <span style={{ fontSize: "10px", color: "#94a3b8", fontWeight: "normal" }}>
                                ({(d.size_bytes / 1024).toFixed(1)} KB)
                              </span>
                            </div>
                            <div style={{ fontSize: "11px", color: "#64748b", marginTop: "2px" }}>
                              Status: <span style={{ color: d.status === "completed" ? "#10b981" : "#ef4444" }}>{d.status}</span> |
                              Type: {d.file_type} | Uploaded: {new Date(d.created_at).toLocaleString()}
                              {d.error_message && <span style={{ color: "#ef4444", marginLeft: "6px" }}>({d.error_message})</span>}
                            </div>
                          </div>
                          <div style={{ display: "flex", gap: "6px" }}>
                            <button
                              className="tool-btn"
                              style={{ background: "#1e293b", border: "1px solid #334155" }}
                              title="View Extracted Text"
                              onClick={() => {
                                authFetch(`http://127.0.0.1:8080/api/documents/${d.id}`)
                                  .then((r) => r.json())
                                  .then((data) => setSelectedDocText({ filename: d.filename, text: data.extracted_text || "(No text)" }));
                              }}
                            >
                              <Eye size={13} color="#38bdf8" /> Text
                            </button>
                            <button
                              className="tool-btn"
                              style={{ background: "#1e293b", border: "1px solid #334155" }}
                              title="Reprocess Document"
                              onClick={() => handleReprocessDoc(d.id)}
                            >
                              <RefreshCw size={13} color="#f59e0b" /> Retry
                            </button>
                            <button
                              className="tool-btn"
                              style={{ background: "#7f1d1d", color: "#fca5a5" }}
                              title="Delete Document"
                              onClick={() => handleDeleteDoc(d.id)}
                            >
                              <Trash2 size={13} />
                            </button>
                          </div>
                        </div>
                      ))
                    )}
                  </div>

                  {/* Extracted Text Viewer Modal / Box */}
                  {selectedDocText && (
                    <div
                      style={{
                        background: "#090d14",
                        border: "1px solid #3b82f6",
                        borderRadius: "6px",
                        padding: "12px",
                        display: "flex",
                        flexDirection: "column",
                        gap: "8px",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <span style={{ fontWeight: 600, fontSize: "12px", color: "#38bdf8" }}>
                          Extracted Text: {selectedDocText.filename}
                        </span>
                        <button
                          onClick={() => setSelectedDocText(null)}
                          style={{ background: "transparent", border: "none", color: "#94a3b8", cursor: "pointer" }}
                        >
                          ✕ Close
                        </button>
                      </div>
                      <pre
                        style={{
                          whiteSpace: "pre-wrap",
                          wordBreak: "break-all",
                          fontSize: "11px",
                          fontFamily: "monospace",
                          color: "#cbd5e1",
                          maxHeight: "180px",
                          overflowY: "auto",
                          background: "#0f172a",
                          padding: "8px",
                          borderRadius: "4px",
                        }}
                      >
                        {selectedDocText.text}
                      </pre>
                    </div>
                  )}
                </div>
              )}

              {/* TAB 2: Extracted Entities Review */}
              {docTab === "entities" && (
                <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div style={{ fontSize: "12px", color: "#94a3b8" }}>
                      Select entities to construct or expand the investigation graph.
                    </div>
                    <div style={{ display: "flex", gap: "8px" }}>
                      <button
                        className="tool-btn"
                        style={{ background: "#1e293b", border: "1px solid #2a3749", fontSize: "11px" }}
                        onClick={() => setSelectedEntityIndices(intelData.canonical_entities.map((_: any, idx: number) => idx))}
                      >
                        Select All
                      </button>
                      <button
                        className="tool-btn"
                        style={{ background: "#1e293b", border: "1px solid #2a3749", fontSize: "11px" }}
                        onClick={() => setSelectedEntityIndices([])}
                      >
                        Deselect All
                      </button>
                    </div>
                  </div>

                  {intelData.canonical_entities.length === 0 ? (
                    <div style={{ fontSize: "13px", color: "#64748b", padding: "20px", textAlign: "center" }}>
                      No entities extracted yet. Upload a document in the Documents tab to extract indicators.
                    </div>
                  ) : (
                    <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                      {intelData.canonical_entities.map((ent: any, idx: number) => {
                        const isSelected = selectedEntityIndices.includes(idx);
                        return (
                          <div
                            key={idx}
                            style={{
                              background: isSelected ? "#1e293b" : "#0f172a",
                              border: `1px solid ${isSelected ? "#3b82f6" : "#2a3749"}`,
                              borderRadius: "6px",
                              padding: "8px 12px",
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "center",
                            }}
                          >
                            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                              <input
                                type="checkbox"
                                checked={isSelected}
                                onChange={(e) => {
                                  if (e.target.checked) {
                                    setSelectedEntityIndices([...selectedEntityIndices, idx]);
                                  } else {
                                    setSelectedEntityIndices(selectedEntityIndices.filter((i) => i !== idx));
                                  }
                                }}
                              />
                              <div>
                                <span style={{ fontWeight: 600, fontSize: "13px" }}>{ent.label}</span>
                                <span
                                  style={{
                                    fontSize: "10px",
                                    marginLeft: "8px",
                                    padding: "2px 6px",
                                    borderRadius: "4px",
                                    background: "#334155",
                                    color: "#cbd5e1",
                                    textTransform: "uppercase",
                                  }}
                                >
                                  {ent.type}
                                </span>
                                <div style={{ fontSize: "11px", color: "#94a3b8", marginTop: "2px" }}>
                                  Mentions: {ent.mention_count} | Confidence: {ent.confidence} | Method: {ent.method}
                                </div>
                              </div>
                            </div>
                            <span style={{ fontSize: "10px", color: "#10b981", background: "rgba(16, 185, 129, 0.1)", padding: "2px 6px", borderRadius: "4px" }}>
                              Verified Excerpt
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}

              {/* TAB 3: Cross-Document Matches */}
              {docTab === "matches" && (
                <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                  <div style={{ fontSize: "12px", color: "#94a3b8" }}>
                    Potential entity duplicates detected across separate documents using token overlap and Gestalt pattern matching.
                  </div>

                  {intelData.match_candidates.length === 0 ? (
                    <div style={{ fontSize: "13px", color: "#64748b", padding: "20px", textAlign: "center" }}>
                      No cross-document match candidates detected. Upload two or more documents with shared entities to view candidates.
                    </div>
                  ) : (
                    <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                      {intelData.match_candidates.map((mc: any, idx: number) => (
                        <div
                          key={idx}
                          style={{
                            background: "#0f172a",
                            border: "1px solid #2a3749",
                            borderRadius: "6px",
                            padding: "10px 14px",
                            display: "flex",
                            flexDirection: "column",
                            gap: "6px",
                          }}
                        >
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                            <div>
                              <span style={{ fontWeight: 700, fontSize: "13px", color: "#38bdf8" }}>
                                {mc.entity1_label || mc.entity_a?.label || "Entity A"}
                              </span>
                              <span style={{ margin: "0 8px", color: "#94a3b8" }}>⟷</span>
                              <span style={{ fontWeight: 700, fontSize: "13px", color: "#38bdf8" }}>
                                {mc.entity2_label || mc.entity_b?.label || "Entity B"}
                              </span>
                              <span style={{ fontSize: "11px", color: "#94a3b8", marginLeft: "6px" }}>({mc.type})</span>
                            </div>
                            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                              <span
                                style={{
                                  fontSize: "11px",
                                  fontWeight: 600,
                                  background: (mc.score ?? mc.match_score ?? 0) >= 0.85 ? "#064e3b" : "#78350f",
                                  color: (mc.score ?? mc.match_score ?? 0) >= 0.85 ? "#34d399" : "#fbbf24",
                                  padding: "2px 8px",
                                  borderRadius: "4px",
                                }}
                              >
                                {(mc.suggested_action || mc.suggestion || "possible_match").replace("_", " ").toUpperCase()} ({(((mc.score ?? mc.match_score ?? 0)) * 100).toFixed(0)}%)
                              </span>
                            </div>
                          </div>
                          <div style={{ fontSize: "11px", color: "#cbd5e1" }}>
                            <b>Evidence:</b> {mc.evidence || (Array.isArray(mc.supporting_evidence) ? mc.supporting_evidence.join("; ") : "Cross-document pattern match")}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* TAB 4: Relationships */}
              {docTab === "relationships" && (
                <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                  <div style={{ fontSize: "12px", color: "#94a3b8" }}>
                    Evidence-backed co-occurrence relationships discovered within sentences and paragraphs.
                  </div>

                  {intelData.relationships.length === 0 ? (
                    <div style={{ fontSize: "13px", color: "#64748b", padding: "20px", textAlign: "center" }}>
                      No relationships extracted yet.
                    </div>
                  ) : (
                    <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                      {intelData.relationships.map((rel: any, idx: number) => {
                        const isSelected = selectedRelIndices.includes(idx);
                        return (
                          <div
                            key={idx}
                            style={{
                              background: isSelected ? "#1e293b" : "#0f172a",
                              border: `1px solid ${isSelected ? "#3b82f6" : "#2a3749"}`,
                              borderRadius: "6px",
                              padding: "8px 12px",
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "center",
                            }}
                          >
                            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                              <input
                                type="checkbox"
                                checked={isSelected}
                                onChange={(e) => {
                                  if (e.target.checked) {
                                    setSelectedRelIndices([...selectedRelIndices, idx]);
                                  } else {
                                    setSelectedRelIndices(selectedRelIndices.filter((i) => i !== idx));
                                  }
                                }}
                              />
                              <div>
                                <span style={{ fontWeight: 600, fontSize: "13px" }}>{rel.source_label}</span>
                                <span style={{ margin: "0 6px", color: "#38bdf8", fontSize: "11px", fontWeight: 700 }}>
                                  [{rel.relationship_type || rel.type}]
                                </span>
                                <span style={{ fontWeight: 600, fontSize: "13px" }}>{rel.target_label}</span>
                                {rel.category && (
                                  <span
                                    style={{
                                      marginLeft: "8px",
                                      fontSize: "10px",
                                      padding: "1px 6px",
                                      borderRadius: "3px",
                                      background:
                                        rel.category === "explicit_relationship"
                                          ? "#065f46"
                                          : rel.category === "rule_derived"
                                          ? "#1e3a8a"
                                          : "#374151",
                                      color:
                                        rel.category === "explicit_relationship"
                                          ? "#6ee7b7"
                                          : rel.category === "rule_derived"
                                          ? "#93c5fd"
                                          : "#9ca3af",
                                      textTransform: "uppercase",
                                    }}
                                  >
                                    {rel.category.replace("_", " ")}
                                  </span>
                                )}
                                <div style={{ fontSize: "11px", color: "#94a3b8", marginTop: "2px" }}>
                                  Excerpt: "{rel.evidence_excerpt}"
                                </div>
                              </div>
                            </div>
                            <span style={{ fontSize: "10px", color: "#f59e0b", background: "rgba(245, 158, 11, 0.1)", padding: "2px 6px", borderRadius: "4px" }}>
                              Confidence: {rel.confidence}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div
              style={{
                padding: "12px 16px",
                borderTop: "1px solid #2a3749",
                background: "#0f141c",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <label style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "12px", color: "#cbd5e1", cursor: "pointer" }}>
                <input
                  type="checkbox"
                  checked={includeDocNodeInGraph}
                  onChange={(e) => setIncludeDocNodeInGraph(e.target.checked)}
                />
                Include Source Document node in Graph
              </label>

              <div style={{ display: "flex", gap: "8px" }}>
                <button
                  className="tool-btn"
                  style={{ background: "#334155" }}
                  onClick={() => setShowDocModal(false)}
                >
                  Close
                </button>
                <button
                  className="tool-btn"
                  style={{ background: "#2563eb", color: "#fff", fontWeight: 600 }}
                  onClick={handleBuildGraphFromIntelligence}
                >
                  <Sparkles size={14} /> Add Selected to Graph ({selectedEntityIndices.length} entities, {selectedRelIndices.length} edges)
                </button>
              </div>
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
            <button
              className="tool-btn"
              aria-pressed={showAllConnections}
              title={showAllConnections ? "Hide inferred and document links" : "Show inferred and document links"}
              onClick={() => setShowAllConnections((visible) => !visible)}
            >
              <Eye size={14} /> {showAllConnections ? "Hide extra links" : "Show all links"}
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

          {selectedEntity && (
            <section className="entity-bookmark-popover" aria-label="Selected entity details">
              <div className="entity-bookmark-header">
                <Bookmark size={15} aria-hidden="true" />
                <span>ENTITY CARD</span>
                <button
                  type="button"
                  className="entity-bookmark-close"
                  aria-label="Close entity card"
                  onClick={() => cyInstance.current?.nodes(":selected").unselect()}
                >
                  <XCircle size={16} />
                </button>
              </div>
              <div className="entity-bookmark-name">{selectedEntity.label}</div>
              <div className="entity-bookmark-type">{selectedEntity.type.replaceAll("_", " ")}</div>
              {selectedGraphMatches.length > 0 ? (
                <div className="entity-match-list">
                  <div className="entity-match-heading">Suggested matches</div>
                  {selectedGraphMatches.slice(0, 4).map((match) => {
                    const peer = match.entity_a.id === selectedEntity.id ? match.entity_b : match.entity_a;
                    return (
                      <div className="entity-match-item" key={`${match.entity_a.id}:${match.entity_b.id}`}>
                        <div className="entity-match-copy">
                          <strong>{peer.label}</strong>
                          <span>{Math.round(match.score * 100)}% · {match.suggestion.replaceAll("_", " ")}</span>
                        </div>
                        <button type="button" className="entity-match-confirm" onClick={() => handleConfirmGraphMatch(match)}>
                          Confirm match
                        </button>
                      </div>
                    );
                  })}
                  <p className="entity-match-note">Dashed links are suggestions; confirmation adds a reviewed graph relationship.</p>
                </div>
              ) : (
                <div className="entity-match-empty">No suggested matches for this entity.</div>
              )}
            </section>
          )}

          {selectedConnection && (
            <section className="entity-bookmark-popover connection-bookmark-popover" aria-label="Selected connection details">
              <div className="entity-bookmark-header">
                <Bookmark size={15} aria-hidden="true" />
                <span>CONNECTION CARD</span>
                <button
                  type="button"
                  className="entity-bookmark-close"
                  aria-label="Close connection card"
                  onClick={() => cyInstance.current?.$(`#${selectedConnection.id}`).unselect()}
                >
                  <XCircle size={16} />
                </button>
              </div>
              <div className="connection-endpoint">{selectedConnection.sourceLabel}</div>
              <div className="connection-type">{selectedConnection.type.replaceAll("_", " ")}</div>
              <div className="connection-endpoint">{selectedConnection.targetLabel}</div>
              <div className="connection-metadata">
                <span>Source: {selectedConnection.provenance.source || "unknown"}</span>
                <span>Method: {selectedConnection.provenance.method || "direct"}</span>
                <span>Confidence: {Math.round((selectedConnection.provenance.confidence ?? 1) * 100)}%</span>
              </div>
              {Object.keys(selectedConnection.properties).length > 0 && (
                <pre className="connection-properties">{JSON.stringify(selectedConnection.properties, null, 2)}</pre>
              )}
            </section>
          )}

          {/* Empty Case or No Active Case Guidance Overlay */}
          {!investigationId ? (
            <div style={{
              position: "absolute", top: "50%", left: "50%", transform: "translate(-50%, -50%)",
              textAlign: "center", pointerEvents: "none", zIndex: 2,
            }}>
              <div style={{
                width: 64, height: 64, borderRadius: "50%", background: "rgba(59,130,246,0.1)",
                display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 16px",
                border: "1px solid rgba(59,130,246,0.2)",
              }}>
                <FolderOpen size={32} color="#38bdf8" />
              </div>
              <h3 style={{ fontSize: 16, fontWeight: 700, color: "#f1f5f9", marginBottom: 6 }}>No Active Investigation</h3>
              <p style={{ fontSize: 13, color: "#64748b", maxWidth: 320, lineHeight: 1.5, margin: "0 auto 16px" }}>
                Select an existing investigation from Cases or create a new case to begin mapping entities.
              </p>
              <button
                onClick={handleCreateInvestigation}
                style={{
                  pointerEvents: "auto", background: "linear-gradient(135deg, #059669, #047857)",
                  border: "none", borderRadius: 6, color: "#fff", padding: "8px 16px",
                  fontSize: 13, fontWeight: 600, cursor: "pointer", display: "inline-flex",
                  alignItems: "center", gap: 6,
                }}
              >
                <Plus size={14} /> Create New Case
              </button>
            </div>
          ) : null}

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
                      setInputDialogValue("Analyst Note");
                      setInputDialogSecondary("");
                      setInputDialogError("");
                      setInputDialog({
                        title: "Attach evidence",
                        initialValue: "Analyst Note",
                        placeholder: "Source identifier",
                        secondaryPlaceholder: "Notes or evidence quote",
                        submitLabel: "Attach evidence",
                        onSubmit: async (sourceId) => {
                          const response = await authFetch(`http://127.0.0.1:8080/api/investigations/${investigationId}/entities/${selectedEntity.id}/evidence`, {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ source_identifier: sourceId, user_notes: inputDialogSecondary }),
                          });
                          const result = await response.json();
                          if (!response.ok) throw new Error(formatAuthError(result, "Could not attach evidence."));
                          setInputDialog(null);
                        },
                      });
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

      {inputDialog && (
        <div className="workflow-modal-backdrop" role="presentation" onMouseDown={(event) => {
          if (event.target === event.currentTarget && !inputDialogBusy) setInputDialog(null);
        }}>
          <form
            className="workflow-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="workflow-dialog-title"
            onSubmit={async (event) => {
              event.preventDefault();
              const value = inputDialogValue.trim();
              if (!value) {
                setInputDialogError("Enter a value to continue.");
                return;
              }
              setInputDialogBusy(true);
              setInputDialogError("");
              try {
                await inputDialog.onSubmit(value);
              } catch (error) {
                setInputDialogError(error instanceof Error ? error.message : "The request failed.");
              } finally {
                setInputDialogBusy(false);
              }
            }}
          >
            <h2 id="workflow-dialog-title">{inputDialog.title}</h2>
            <input
              autoFocus
              value={inputDialogValue}
              placeholder={inputDialog.placeholder}
              onChange={(event) => setInputDialogValue(event.target.value)}
            />
            {inputDialog.secondaryPlaceholder && (
              <textarea
                value={inputDialogSecondary}
                placeholder={inputDialog.secondaryPlaceholder}
                onChange={(event) => setInputDialogSecondary(event.target.value)}
              />
            )}
            {inputDialogError && <p className="workflow-modal-error">{inputDialogError}</p>}
            <div className="workflow-modal-actions">
              <button type="button" className="workflow-secondary-button" onClick={() => setInputDialog(null)} disabled={inputDialogBusy}>Cancel</button>
              <button type="submit" className="workflow-primary-button" disabled={inputDialogBusy}>
                {inputDialogBusy ? "Working..." : inputDialog.submitLabel}
              </button>
            </div>
          </form>
        </div>
      )}

      {showReportDialog && (
        <div className="workflow-modal-backdrop" role="presentation" onMouseDown={(event) => {
          if (event.target === event.currentTarget && !reportBusy) setShowReportDialog(false);
        }}>
          <section className="workflow-modal report-download-modal" role="dialog" aria-modal="true" aria-labelledby="report-dialog-title">
            <div className="report-modal-icon"><FileText size={20} /></div>
            <h2 id="report-dialog-title">Download case report</h2>
            <p>Generate a PDF report for <strong>{investigations.find((item) => item.id === investigationId)?.title || "this case"}</strong>.</p>
            {inputDialogError && <p className="workflow-modal-error">{inputDialogError}</p>}
            <div className="workflow-modal-actions">
              <button type="button" className="workflow-secondary-button" onClick={() => setShowReportDialog(false)} disabled={reportBusy}>Cancel</button>
              <button type="button" className="workflow-primary-button" onClick={downloadInvestigationReport} disabled={reportBusy}>
                <Download size={15} /> {reportBusy ? "Preparing PDF..." : "Download PDF"}
              </button>
            </div>
          </section>
        </div>
      )}
    </>
  );
};

export default App;
