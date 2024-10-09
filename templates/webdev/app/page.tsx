"use client"

import React, { useState } from "react";
import Link from "next/link"
import styles from "@/styles/webdev.module.css";
import Answer from "@/components/answer"

const R2RQueryApp: React.FC = () => {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const performQuery = async () => {
    setIsLoading(true);
    setResult("");

    try {
      const response = await fetch("/api/rag", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ query }),
      });
      
      if (!response.ok) {
        throw new Error("Network response was not ok");
      }
      
      const { message } = await response.json()
      setResult(message);
    } catch (error) {
      setResult(
        `Error: ${error instanceof Error ? error.message : String(error)}`,
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className={styles.appWrapper}>
      <h1 className={styles.title}>R2R Web Dev Template</h1>
      <p>
        {" "}
        A simple template for making RAG queries with R2R. Make sure that your
        R2R server is up and running, and that you've ingested files!
      </p>
      <p>
        Check out the{" "}
        <a
          href="https://r2r-docs.sciphi.ai/"
          target="_blank"
          rel="noopener noreferrer"
        >
          R2R Documentation
        </a>{" "}
        for more information.
      </p>
      <p>Also available in this template are <Link href="/agent">Agent</Link> and <Link href="/search">Search</Link> examples</p>
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Enter your query here"
        className={styles.queryInput}
      />
      <button
        onClick={performQuery}
        disabled={isLoading}
        className={styles.submitButton}
      >
        Submit Query
      </button>
      {isLoading ? (
        <div className={styles.spinner} />
      ) : (
        <div className={styles.resultDisplay}>
          <Answer message = {result}/></div>
      )}
    </div>
  );
};

export default R2RQueryApp;
