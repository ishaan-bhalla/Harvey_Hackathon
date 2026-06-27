import { useEffect, useRef, useState } from "react";

const BASE_URL = "http://127.0.0.1:8000";

const TOPIC_COLORS = {
  horizon_system: "#3b82f6",
  knowledge: "#8b5cf6",
  prosecutions: "#ef4444",
  management: "#f59e0b",
  financial_losses: "#10b981",
  other: "#6b7280"
};

const ORG_COLORS = {
  "Fujitsu": "#f59e0b",
  "Post Office": "#3b82f6",
  "Other": "#6b7280"
};

const VERDICT_COLORS = {
  SUPPORTS: "#22c55e",
  CONTRADICTS: "#ef4444",
  NOT_ADDRESSED: "#374151"
};

export default function GraphView() {
  const canvasRef = useRef(null);
  const [graphData, setGraphData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    fetch(`${BASE_URL}/graph`)
      .then(r => r.json())
      .then(data => {
        setGraphData(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!graphData || !canvasRef.current) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    const W = canvas.width;
    const H = canvas.height;
    ctx.clearRect(0, 0, W, H);

    const witnesses = graphData.witnesses || [];
    const allegations = graphData.allegations || [];
    const relationships = graphData.relationships || [];

    // Position witnesses on left, allegations on right
    const witnessPositions = {};
    witnesses.forEach((w, i) => {
      witnessPositions[w.name] = {
        x: 180,
        y: 80 + i * (H - 100) / Math.max(witnesses.length - 1, 1),
        ...w
      };
    });

    const allegationPositions = {};
    allegations.forEach((a, i) => {
      allegationPositions[a.id] = {
        x: W - 180,
        y: 80 + i * (H - 100) / Math.max(allegations.length - 1, 1),
        ...a
      };
    });

    // Draw relationships
    relationships.forEach(rel => {
      const from = witnessPositions[rel.witness];
      const to = allegationPositions[rel.allegation_id];
      if (!from || !to) return;
      ctx.beginPath();
      ctx.moveTo(from.x, from.y);
      ctx.lineTo(to.x, to.y);
      ctx.strokeStyle = VERDICT_COLORS[rel.verdict] || "#374151";
      ctx.lineWidth = rel.verdict === "CONTRADICTS" ? 2.5 : 1;
      ctx.globalAlpha = rel.verdict === "NOT_ADDRESSED" ? 0.1 : 0.6;
      ctx.stroke();
      ctx.globalAlpha = 1;
    });

    // Draw witness nodes
    Object.values(witnessPositions).forEach(w => {
      ctx.beginPath();
      ctx.arc(w.x, w.y, 28, 0, Math.PI * 2);
      ctx.fillStyle = ORG_COLORS[w.org] || "#6b7280";
      ctx.fill();
      ctx.strokeStyle = "#1f2937";
      ctx.lineWidth = 2;
      ctx.stroke();
      ctx.fillStyle = "white";
      ctx.font = "bold 9px Inter, sans-serif";
      ctx.textAlign = "center";
      const words = w.name.split(" ");
      const lastName = words[words.length - 1];
      ctx.fillText(lastName, w.x, w.y + 3);

      // Org label
      ctx.fillStyle = ORG_COLORS[w.org] || "#6b7280";
      ctx.font = "8px Inter, sans-serif";
      ctx.fillText(w.org, w.x - 50, w.y);
    });

    // Draw allegation nodes
    Object.values(allegationPositions).forEach(a => {
      const color = TOPIC_COLORS[a.topic] || "#6b7280";
      ctx.beginPath();
      ctx.arc(a.x, a.y, 22, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
      ctx.strokeStyle = "#1f2937";
      ctx.lineWidth = 2;
      ctx.stroke();
      ctx.fillStyle = "white";
      ctx.font = "bold 10px Inter, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(a.id, a.x, a.y + 4);

      // Topic label
      ctx.fillStyle = color;
      ctx.font = "8px Inter, sans-serif";
      ctx.fillText(a.topic.replace("_", " "), a.x + 30, a.y);
    });

  }, [graphData]);

  if (loading) return (
    <div className="flex items-center justify-center h-64 text-gray-400">
      Loading relationship graph...
    </div>
  );

  if (!graphData || !graphData.witnesses?.length) return (
    <div className="flex items-center justify-center h-64 text-gray-400">
      No graph data yet. Run an analysis first.
    </div>
  );

  return (
    <div className="bg-gray-900 rounded-lg p-4">
      <h3 className="text-white font-semibold mb-2 text-sm uppercase tracking-wider">
        Witness — Allegation Relationship Network
      </h3>
      <div className="flex gap-4 mb-3 text-xs">
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded-full bg-green-500 inline-block"></span>
          <span className="text-gray-400">Supports</span>
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded-full bg-red-500 inline-block"></span>
          <span className="text-gray-400">Contradicts</span>
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded-full bg-yellow-500 inline-block"></span>
          <span className="text-gray-400">Fujitsu witness</span>
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded-full bg-blue-500 inline-block"></span>
          <span className="text-gray-400">Post Office witness</span>
        </span>
      </div>
      <canvas
        ref={canvasRef}
        width={800}
        height={500}
        className="w-full rounded"
        style={{background: "#111827"}}
      />
    </div>
  );
}
