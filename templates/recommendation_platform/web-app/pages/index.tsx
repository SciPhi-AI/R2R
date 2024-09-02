import { useState, useEffect } from "react";
import POPOSMap from "@/components/POPOSMap";
import { parse } from "csv-parse/sync";
import DynamicSearchBar from "@/components/DynamicSearchBar";

interface POPOS {
  NAME: string;
  POPOS_ADDRESS: string;
  HOURS: string;
  latitude: string;
  longitude: string;
  [key: string]: string;
}

interface SearchResult {
  address: string;
  latitude: number;
  longitude: number;
  description: string;
}

export default function Home() {
  const [poposData, setPoposData] = useState<POPOS[]>([]);
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const agentUrl =
    process.env.NEXT_PUBLIC_DEFAULT_AGENT_URL || "defaultAgentUrl";

  useEffect(() => {
    fetch("/data/Privately_Owned_Public_Open_Spaces_20240809.csv")
      .then((response) => response.text())
      .then((csvString) => {
        const records = parse(csvString, {
          columns: true,
          skip_empty_lines: true,
        }) as POPOS[];
        setPoposData(records);
      });
  }, []);

  const handleSearchResults = (results: SearchResult[]) => {
    setSearchResults(results);
  };

  return (
    <main className="min-h-screen p-4 sm:p-8 md:p-12 bg-[#C5D86D]">
      <div className="border-2 border-[#414233] p-4 sm:p-8 md:p-12 rounded-3xl shadow-lg">
        <header className="text-center mb-8">
          <div className="inline-block px-4 py-2 mb-6">
            <h2 className="text-sm tracking-widest">SAN FRANCISCO</h2>
          </div>
          <h1 className="text-3xl sm:text-4xl md:text-5xl font-bold mb-4 text-[#414233]">
            Privately Owned Public Open Spaces
          </h1>
          <p className="text-base sm:text-lg text-[#414233] max-w-3xl mx-auto">
            POPOS are publicly accessible spaces in forms of plazas, terraces,
            atriums, small parks, and even snippets which are provided and
            maintained by private developers. In San Francisco, POPOS mostly
            appear in the Downtown office district area.
          </p>
        </header>
        <section className="flex flex-col md:flex-row mb-8">
          <div className="w-full md:w-2/3 pr-0 md:pr-4 mb-4 md:mb-0">
            <POPOSMap poposData={poposData} searchResults={searchResults} />
          </div>
          <div className="w-full md:w-1/3 pl-0 md:pl-4">
            <h2 className="text-xl font-bold mb-4">I&apos;m looking to...</h2>
            <DynamicSearchBar
              onSearchResults={handleSearchResults}
              agentUrl={agentUrl}
              setIsLoading={setIsLoading}
            />
          </div>
        </section>
        <div className="text-center">
        <p className="text-sm text-[#414233] mt-4">
              This demo incorporates a natural language recommendation feature
              powered by RAG over publically available data from{" "}
              <a
                href="https://data.sfgov.org/Culture-and-Recreation/Privately-Owned-Public-Open-Spaces/65ik-7wqd/data"
                target="_blank"
                rel="noopener noreferrer"
                className="text-white"
              >
                DataSF
              </a>
              . Inspired by{" "}
              <a
                href="https://sfpopos.com"
                target="_blank"
                rel="noopener noreferrer"
                className="text-white"
              >
                sfpopos.com
              </a>
              .
            </p>
          </div>
      </div>
    </main>
  );
}
