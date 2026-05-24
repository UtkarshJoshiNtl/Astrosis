import { createFileRoute } from "@tanstack/react-router";
import { useState, useEffect } from "react";
import { PageShell, useUtcClock } from "@/components/shell/Chrome";
import { useHealth } from "@/hooks/useAstrosisData";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

export const Route = createFileRoute("/docs")({
  component: DocsPage,
});

const DOC_FILES = [
  { id: "architecture", label: "Architecture" },
  { id: "design", label: "Design Decisions" },
  { id: "performance", label: "Performance" },
  { id: "validation", label: "Validation" },
];

const DOC_LABELS: Record<string, string> = {
  architecture: "Architecture",
  design: "Design Decisions",
  performance: "Performance",
  validation: "Validation",
};

function DocsPage() {
  const health = useHealth();
  const utc = useUtcClock();
  const backendLabel = health.data?.backend ?? "—";
  const [activeDoc, setActiveDoc] = useState("architecture");
  const [contents, setContents] = useState<Record<string, string>>({});

  useEffect(() => {
    for (const doc of DOC_FILES) {
      if (contents[doc.id]) continue;
      fetch(`/docs/${doc.id}.md`)
        .then((res) => res.text())
        .then((text) => setContents((prev) => ({ ...prev, [doc.id]: text })))
        .catch(() => setContents((prev) => ({ ...prev, [doc.id]: `# ${doc.label}\n\nFailed to load document.` })));
    }
  }, [contents]);

  const content = contents[activeDoc] ?? `# ${DOC_LABELS[activeDoc] ?? activeDoc}\n\nLoading...`;

  return (
    <PageShell backendLabel={backendLabel} health={health.data}>
      <div className="h-full flex">
        <div className="w-48 surface hairline-r p-3 text-[11px] space-y-1">
          {DOC_FILES.map((doc) => (
            <button
              key={doc.id}
              onClick={() => setActiveDoc(doc.id)}
              className={`block w-full text-left px-2 py-1 ${
                activeDoc === doc.id ? "bg-[var(--surface-2)] text-foreground" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {doc.label}
            </button>
          ))}
        </div>
        <div className="flex-1 p-4 overflow-auto">
          <div className="prose prose-invert prose-sm max-w-none">
            <Markdown remarkPlugins={[remarkGfm]}>{content}</Markdown>
          </div>
        </div>
      </div>
    </PageShell>
  );
}
