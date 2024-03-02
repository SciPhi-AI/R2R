"use client";
import { Answer } from "@/app/components/answer";
import { Sources } from "@/app/components/sources";
import { Source } from "@/app/interfaces/source";
import { parseStreaming } from "@/app/utils/parse-streaming";
import { Annoyed } from "lucide-react";
import { FC, useEffect, useState } from "react";

export const Result: FC<{ query: string; rid: string }> = ({ query, rid }) => {
  const [sources, setSources] = useState<Source[]>([]);
  const [markdown, setMarkdown] = useState<string>("");
  const [error, setError] = useState<number | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    // Debounce time in milliseconds
    const debounceTime = 500;
    // Clear the previous timeout if the query changes before the debounce time has passed
    const timeoutId = setTimeout(() => {
      void parseStreaming(
        controller,
        query,
        rid,
        setSources,
        setMarkdown,
        setError,
      );
    }, debounceTime);
    // Cleanup function to clear the timeout when the component unmounts or the query changes
    return () => {
      controller.abort();
      clearTimeout(timeoutId);
    };
  }, [query]);
  return (
    <div className="flex flex-col gap-8">
      <Answer markdown={markdown} sources={sources}></Answer>
      {error && (
        <div className="absolute inset-4 flex items-center justify-center bg-white/40 backdrop-blur-sm">
          <div className="p-4 bg-white shadow-2xl rounded text-blue-500 font-medium flex gap-4">
            <Annoyed></Annoyed>
            {error === 429
              ? "Sorry, you have made too many requests recently, try again later."
              : "Sorry, we might be overloaded, try again later."}
          </div>
        </div>
      )}
      <Sources sources={sources}></Sources>
    </div>
  );
};
