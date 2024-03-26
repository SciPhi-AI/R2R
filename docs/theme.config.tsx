import React from "react";
import { DocsThemeConfig } from "nextra-theme-docs";

const config: DocsThemeConfig = {
  logo: <span>R2R</span>,
  project: {
    link: "https://github.com/SciPhi-AI/R2R",
  },
  chat: {
    link: "https://discord.gg/p6KqD2kjtB",
  },
  docsRepositoryBase: "https://github.com/SciPhi-AI/R2R",
  footer: {
    text: "EmergentAGI, Inc. © 2024",
  },
  head: (
    <>
      <meta property="og:title" content="R2R Documentation" />
      <meta
        property="og:description"
        content="Documentation for the R2R Framework"
      />
      <meta property="og:image" content="./public/r2r_mini.png" />
    </>
  ),
};

export default config;
