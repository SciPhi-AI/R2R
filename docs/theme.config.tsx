import React from "react";
import { DocsThemeConfig } from "nextra-theme-docs";

const config: DocsThemeConfig = {
  logo: <span>SciPhi</span>,
  logoLink: "https://github.com/SciPhi-AI/R2R",
  // logo: (
  //   <img width={120} src="./public/r2r_mini.png" style={{ borderRadius: 5 }} />
  // ),
  head: (
    <>
      <link rel="icon" type="image/png" href="./favicon.png" />
      <meta property="og:title" content="R2R Documentation" />
      <meta
        property="og:description"
        content="The official documentation for the Rag2Riches (R2R) framework."
      />
      <meta property="og:image" content="./public/r2r_mini.png" />
    </>
  ),
  project: {
    link: "https://github.com/SciPhi-AI/R2R",
  },
  chat: {
    link: "https://discord.gg/p6KqD2kjtB",
  },
  docsRepositoryBase: "https://github.com/SciPhi-AI/R2R/tree/main/docs",
  footer: {
    text: `EmergentAGI, Inc. © ${new Date().getFullYear()}`,
  },
  useNextSeoProps() {
    return {
      titleTemplate: "%s",
    };
  },
};

export default config;
