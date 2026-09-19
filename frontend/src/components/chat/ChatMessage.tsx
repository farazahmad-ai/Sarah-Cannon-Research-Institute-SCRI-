import { Bot, User } from "lucide-react";

export interface MessageProps {
  role: "user" | "assistant" | "system";
  content: string;
  createdAt?: string;
  isStreaming?: boolean;
}

export function ChatMessage({
  role,
  content,
  createdAt,
  isStreaming = false,
}: MessageProps) {
  const isUser = role === "user";

  // Formats inline bracketed citations [NCTxxxx, Section] with clinical badge styling
  const renderFormattedContent = (text: string) => {
    // Regex matching [NCT..., ...] citations
    const citationRegex = /\[(NCT\d{8}[^\]]*)\]/g;
    const parts = [];
    let lastIndex = 0;
    let match;

    while ((match = citationRegex.exec(text)) !== null) {
      if (match.index > lastIndex) {
        parts.push(text.slice(lastIndex, match.index));
      }
      parts.push(
        <span
          key={match.index}
          className="inline-flex items-center gap-1 font-mono text-xs text-sky-300 bg-sky-950/80 border border-sky-800/60 px-1.5 py-0.5 rounded mx-1 my-0.5 shadow-xs select-all"
        >
          {match[0]}
        </span>
      );
      lastIndex = match.index + match[0].length;
    }

    if (lastIndex < text.length) {
      parts.push(text.slice(lastIndex));
    }

    return parts.length > 0 ? parts : text;
  };

  if (isUser) {
    return (
      <div className="flex justify-end mb-4 group">
        <div className="flex items-end gap-2 max-w-[85%] md:max-w-[75%]">
          <div className="flex flex-col items-end">
            <div className="bg-sky-600 text-white rounded-2xl rounded-br-xs px-4 py-3 shadow-md text-sm leading-relaxed whitespace-pre-wrap select-text">
              {content}
            </div>
            {createdAt && (
              <span className="text-[11px] text-slate-500 mt-1 mr-1">
                {new Date(createdAt).toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </span>
            )}
          </div>
          <div className="w-7 h-7 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-300 shrink-0 mb-4">
            <User className="w-4 h-4" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start mb-5 group">
      <div className="flex items-start gap-3 max-w-[90%] md:max-w-[80%]">
        <div className="w-8 h-8 rounded-xl bg-sky-950/90 border border-sky-800/60 flex items-center justify-center text-sky-400 shrink-0 shadow-sm mt-0.5">
          <Bot className="w-4 h-4" />
        </div>
        <div className="flex-1 flex flex-col items-start">
          <div className="w-full bg-slate-900/90 border border-slate-800 rounded-2xl rounded-tl-xs p-4 shadow-sm text-slate-200 text-sm leading-relaxed whitespace-pre-wrap select-text">
            {renderFormattedContent(content)}
            {isStreaming && (
              <span className="inline-block w-2 h-4 ml-1 bg-sky-400 animate-pulse align-middle rounded-xs" />
            )}
          </div>
          <div className="flex items-center gap-2 mt-1 ml-1">
            <span className="text-[11px] font-medium text-slate-400">
              SCRI Protocol Copilot
            </span>
            {createdAt && (
              <span className="text-[11px] text-slate-500">
                •{" "}
                {new Date(createdAt).toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
