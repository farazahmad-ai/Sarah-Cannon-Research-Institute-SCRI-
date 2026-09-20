import { useState, useCallback, useRef } from "react";
import { api } from "@/lib/api";

export interface ChatMessageItem {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  createdAt?: Date;
}

interface UseChatStreamOptions {
  threadId?: string;
  onThreadCreated?: (threadId: string) => void;
  onError?: (err: Error) => void;
}

export function useChatStream({
  threadId,
  onThreadCreated,
  onError,
}: UseChatStreamOptions = {}) {
  const [messages, setMessages] = useState<ChatMessageItem[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);

  const handleInputChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    setInput(e.target.value);
  };

  const stop = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsLoading(false);
  }, []);

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || isLoading) return;

      let currentThreadId = threadId;

      // If no thread exists yet, create one first so URL and sidebar synchronize
      if (!currentThreadId) {
        try {
          const newThread = await api.chat.createThread(trimmed.slice(0, 60));
          currentThreadId = newThread.id;
          onThreadCreated?.(newThread.id);
        } catch (err) {
          console.error("Failed to create thread:", err);
          onError?.(err as Error);
          return;
        }
      }

      const userMessage: ChatMessageItem = {
        id: crypto.randomUUID(),
        role: "user",
        content: trimmed,
        createdAt: new Date(),
      };

      const assistantMessageId = crypto.randomUUID();
      const assistantMessage: ChatMessageItem = {
        id: assistantMessageId,
        role: "assistant",
        content: "",
        createdAt: new Date(),
      };

      setMessages((prev) => [...prev, userMessage, assistantMessage]);
      setInput("");
      setIsLoading(true);

      const abortController = new AbortController();
      abortControllerRef.current = abortController;

      try {
        const response = await api.chat.stream({
          thread_id: currentThreadId,
          message: trimmed,
        });

        if (!response.body) {
          throw new Error("No response stream body received.");
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let accumulatedAssistantText = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";

          for (const line of lines) {
            const trimmedLine = line.trim();
            if (!trimmedLine) continue;

            // Vercel AI SDK text part: 0:"<token>"
            if (trimmedLine.startsWith("0:")) {
              try {
                const token = JSON.parse(trimmedLine.slice(2));
                accumulatedAssistantText += token;
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === assistantMessageId
                      ? { ...msg, content: accumulatedAssistantText }
                      : msg
                  )
                );
              } catch (e) {
                console.error("Error parsing stream token:", trimmedLine, e);
              }
            } else if (trimmedLine.startsWith("3:")) {
              // Vercel AI SDK error frame
              try {
                const errDetail = JSON.parse(trimmedLine.slice(2));
                throw new Error(errDetail);
              } catch (e) {
                if (e instanceof Error) throw e;
                throw new Error(trimmedLine.slice(2));
              }
            }
          }
        }
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          console.error("Streaming error:", err);
          onError?.(err as Error);
        }
      } finally {
        setIsLoading(false);
        abortControllerRef.current = null;
      }
    },
    [threadId, isLoading, onThreadCreated, onError]
  );

  const handleSubmit = (e?: React.FormEvent<HTMLFormElement>) => {
    e?.preventDefault();
    sendMessage(input);
  };

  return {
    messages,
    setMessages,
    input,
    setInput,
    handleInputChange,
    handleSubmit,
    sendMessage,
    isLoading,
    stop,
  };
}
