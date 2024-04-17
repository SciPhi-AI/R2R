import React from "react";
import { DocsThemeConfig } from "nextra-theme-docs";
import InkeepChatButton from "./components/InkeepChatButton";

const config: DocsThemeConfig = {
  logo: (
    <>
      <img
        src="/favicon.ico"
        alt="SciPhi Favicon"
        style={{ marginRight: "8px" }}
      />
      <span>SciPhi</span>
    </>
  ),
  logoLink: "https://github.com/SciPhi-AI/R2R",
  head: (
    <>
      <link rel="icon" type="image/png" href="/favicon.ico" />
      <meta property="og:title" content="R2R Documentation" />
      <meta
        property="og:description"
        content="The official documentation for the RAG to Riches (R2R) framework."
      />
      <meta property="og:image" content="/r2r_mini.jpg" />
    </>
  ),
  darkMode: true,
  project: {
    link: "https://github.com/SciPhi-AI/R2R",
  },
  chat: {
    link: "https://discord.gg/p6KqD2kjtB",
  },
  docsRepositoryBase: "https://github.com/SciPhi-AI/R2R/tree/main/docs",
  footer: {
    text: `EmergentAGI, Inc. © ${new Date().getFullYear()}`,
    component: () => <InkeepChatButton />,
  },
  useNextSeoProps() {
    return {
      titleTemplate: "%s",
    };
  },
};

export default config;
