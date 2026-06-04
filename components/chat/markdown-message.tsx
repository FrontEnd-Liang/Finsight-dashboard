"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "@/lib/utils";

interface MarkdownMessageProps {
  content: string;
  className?: string;
}

export function MarkdownMessage({ content, className }: MarkdownMessageProps) {
  return (
    <div
      className={cn(
        "prose prose-invert prose-sm max-w-none font-sans",
        "prose-headings:text-terminal-green prose-headings:font-mono prose-headings:text-sm",
        "prose-p:text-foreground/90 prose-p:leading-relaxed",
        "prose-strong:text-terminal-amber prose-code:text-terminal-green",
        "prose-code:bg-terminal-panel prose-code:px-1 prose-code:rounded",
        "prose-pre:bg-terminal-panel prose-pre:border prose-pre:border-terminal-border",
        "prose-a:text-terminal-green prose-li:marker:text-terminal-green",
        "prose-table:text-xs prose-th:border-terminal-border prose-th:bg-terminal-panel",
        "prose-td:border-terminal-border prose-table:border-collapse",
        className
      )}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          table: ({ children }) => (
            <div className="my-3 overflow-x-auto rounded border border-terminal-border">
              <table className="min-w-full divide-y divide-terminal-border">
                {children}
              </table>
            </div>
          ),
          th: ({ children }) => (
            <th className="px-3 py-2 text-left font-mono text-terminal-green">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="px-3 py-2 border-t border-terminal-border/50">
              {children}
            </td>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
