<p align="left">
  <a href="https://r2r-docs.sciphi.ai"><img src="https://img.shields.io/badge/docs.sciphi.ai-3F16E4" alt="Docs"></a>
  <a href="https://discord.gg/p6KqD2kjtB"><img src="https://img.shields.io/discord/1120774652915105934?style=social&logo=discord" alt="Discord"></a>
  <a href="https://github.com/SciPhi-AI/R2R"><img src="https://img.shields.io/github/stars/SciPhi-AI/R2R" alt="Github Stars"></a>
  <a href="https://github.com/SciPhi-AI/R2R/pulse"><img src="https://img.shields.io/github/commit-activity/w/SciPhi-AI/R2R" alt="Commits-per-week"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-purple.svg" alt="License: MIT"></a>
  <a href="https://www.npmjs.com/package/r2r-js"><img src="https://img.shields.io/npm/v/r2r-js.svg" alt="npm version"></a>
</p>

<img src="https://raw.githubusercontent.com/SciPhi-AI/R2R/main/assets/r2r.png" alt="R2R">
<h3 align="center">
R2R Web Dev Template: A Next.js Starter for Building RAG-powered Web Apps
</h3>

# About

A simple web app template for starting applications with [R2R](https://github.com/SciPhi-AI/R2R). This template demonstrates how to integrate R2R's powerful RAG capabilities into a Next.js web interface, providing a foundation for more complex applications.

For a complete view of how to use R2R for web development, check out the [web dev cookbook](https://r2r-docs.sciphi.ai/cookbooks/web-dev).

<img src="./assets/r2r_webdev_template.png" alt="R2R Web Dev Template">

## Key Features

- **📁 Multimodal Support**: Ingest files ranging from `.txt`, `.pdf`, `.json` to `.png`, `.mp3`, and more.
- **🔍 Hybrid Search**: Combine semantic and keyword search with reciprocal rank fusion for enhanced relevancy.
- **🔗 Graph RAG**: Automatically extract relationships and build knowledge graphs.
- **🗂️ App Management**: Efficiently manage documents and users with rich observability and analytics.
- **🌐 Client-Server**: RESTful API support out of the box.
- **🧩 Configurable**: Provision your application using intuitive configuration files.
- **🔌 Extensible**: Develop your application further with easy builder + factory pattern.
- **🖥️ Dashboard**: Use the [R2R Dashboard](https://github.com/SciPhi-AI/R2R-Dashboard), an open-source React+Next.js app for a user-friendly interaction with R2R.

# Getting Started

1. Clone the repository:
   ```bash
   git clone https://github.com/SciPhi-AI/r2r-webdev-template.git
   cd r2r-webdev-template/r2r-webdev-template
   ```

2. Install dependencies:
   ```bash
   pnpm install
   ```

3. Make sure your R2R server is running.

4. Start the development server:
   ```bash
   pnpm dev
   ```

5. Open [http://localhost:3000](http://localhost:3000) in your browser to see the app.

# Customization

- Update the R2R server URL in `pages/api/r2r-query.ts` if needed.
- Modify the UI in `pages/index.tsx` to fit your needs.
- Add additional pages or components as your application grows.

# Community and Support

- [Discord](https://discord.gg/p6KqD2kjtB): Chat live with maintainers and community members
- [Github Issues](https://github.com/SciPhi-AI/r2r-webdev-template/issues): Report bugs and request features

**Explore our [R2R Docs](https://r2r-docs.sciphi.ai/) for tutorials and cookbooks on various R2R features and integrations.**

# Contributing

We welcome contributions of all sizes! Here's how you can help:

- Open a PR for new features, improvements, or better documentation.
- Submit a [feature request](https://github.com/SciPhi-AI/r2r-webdev-template/issues/new?assignees=&labels=&projects=&template=feature_request.md&title=) or [bug report](https://github.com/SciPhi-AI/r2r-webdev-template/issues/new?assignees=&labels=&projects=&template=bug_report.md&title=)

### Our Contributors

<a href="https://github.com/SciPhi-AI/R2R/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=SciPhi-AI/R2R" />
</a>
