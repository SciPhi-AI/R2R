import React, { useState, useEffect, useRef } from "react";
import { ArrowRight } from "lucide-react";

const activities = [
  "Find a new coffee shop",
  "Soak in the sun",
  "Eat some clam chowder",
  "Look out at the bay",
  "Get some work done",
  "Look at some local art",
];

interface SearchResult {
  address: string;
  latitude: number;
  longitude: number;
  description: string;
}

interface DynamicSearchBarProps {
  onSearchResults: (results: SearchResult[]) => void;
  agentUrl: string;
  setIsLoading: (isLoading: boolean) => void;
}

const DynamicSearchBar: React.FC<DynamicSearchBarProps> = ({
  onSearchResults,
  agentUrl,
  setIsLoading,
}) => {
  const [searchTerm, setSearchTerm] = useState("");
  const [placeholderText, setPlaceholderText] = useState("");
  const [currentActivity, setCurrentActivity] = useState(0);
  const [responseMessage, setResponseMessage] = useState("");
  const [isFocused, setIsFocused] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentActivity((prev) => (prev + 1) % activities.length);
    }, 3000);

    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (!isFocused && !searchTerm) {
      let i = 0;
      const intervalId = setInterval(() => {
        setPlaceholderText(activities[currentActivity].slice(0, i));
        i++;
        if (i > activities[currentActivity].length) {
          clearInterval(intervalId);
        }
      }, 100);

      return () => clearInterval(intervalId);
    }
  }, [currentActivity, isFocused, searchTerm]);

  const handleFocus = () => setIsFocused(true);
  const handleBlur = () => setIsFocused(false);

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setIsSearching(true);
    setIsLoading(true);
    try {
      const response = await fetch("/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: searchTerm,
          agentUrl: agentUrl,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const text = await response.text();
      const completionMatch = text.match(
        /<completion>([\s\S]*?)<\/completion>/,
      );
      if (completionMatch) {
        const completionContent = completionMatch[1].trim();
        const searchResults = extractSearchResults(completionContent);
        setResponseMessage("Search completed successfully.");
        onSearchResults(searchResults);
      } else {
        throw new Error("No completion tag found in the response");
      }
    } catch (error) {
      console.error("Error fetching data:", error);
      setResponseMessage("An error occurred while searching.");
      onSearchResults([]);
    } finally {
      setIsSearching(false);
      setIsLoading(false);
    }
  };

  const extractSearchResults = (content: string): SearchResult[] => {
    const results: SearchResult[] = [];
    const entries = content.match(/\[([^\]]+)\]/g) || [];

    entries.forEach((entry) => {
      const [address, lat, lon, description] = entry
        .slice(1, -1)
        .split(",")
        .map((item) => item.trim());
      const latitude = parseFloat(lat);
      const longitude = parseFloat(lon);

      if (!isNaN(latitude) && !isNaN(longitude) && address && description) {
        results.push({
          address,
          latitude,
          longitude,
          description: description.replace(/^"|"$/g, ""),
        });
      }
    });

    return results;
  };

  return (
    <form onSubmit={handleSubmit} className="w-full relative">
      <div className="flex items-center bg-white rounded-full overflow-hidden shadow-lg transition-all duration-300 focus-within:shadow-xl">
        <input
          ref={inputRef}
          type="text"
          className="flex-grow bg-transparent text-[#414233] px-4 py-3 focus:outline-none"
          placeholder={isFocused || searchTerm ? "" : placeholderText}
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          onFocus={handleFocus}
          onBlur={handleBlur}
          disabled={isSearching}
        />
        <button
          type="submit"
          className={`bg-blue text-black p-3 rounded-full transition-colors duration-200 ${isSearching ? "cursor-not-allowed opacity-50" : "hover:bg-blue500"}`}
          disabled={isSearching}
        >
          {isSearching ? "Searching..." : <ArrowRight size={20} />}
        </button>
      </div>
    </form>
  );
};

export default DynamicSearchBar;
