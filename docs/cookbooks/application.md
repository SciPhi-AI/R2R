---
title: Application
subtitle: Learn how to set up and use the R2R Application for managing your instance.
icon: display
slug: cookbooks/application
---


R2R offers an [open-source React+Next.js application](https://github.com/SciPhi-AI/R2R-Application) designed to give developers an administrative portal for their R2R deployment, and users an application to communicate with out of the box.

## Setup

### Install PNPM

PNPM is a fast, disk space-efficient package manager. To install PNPM, visit the [official PNPM installation page](https://pnpm.io/installation) or follow these instructions:

<AccordionGroup>

<Accordion icon="terminal" title="PNPM Installation">
For Unix-based systems (Linux, macOS):

```zsh
curl -fsSL https://get.pnpm.io/install.sh | sh -
```

For Windows:

```powershell
iwr https://get.pnpm.io/install.ps1 -useb | iex
```

After installation, you may need to add PNPM to your system's PATH.
</Accordion>

</AccordionGroup>

### Installing and Running the R2R Dashboard

If you're running R2R with the Docker, you already have the R2R application running! Just navigate to [http://localhost:7273](http://localhost:7273).

If you're running R2R outside of Docker, run the following commands to install the R2R Dashboard.

1. Clone the project repository and navigate to the project directory:

```zsh
git clone https://github.com/SciPhi-AI/R2R.git
cd R2R-Application
```

2. Install the project dependencies:

```zsh
pnpm install
```

3. Build and start the application for production:

```zsh
pnpm build
pnpm start
```

The dashboard will be available at [http://localhost:3000](http://localhost:3000).

## Features

### Login

To interact with R2R with the dashboard, you must first login. If it's your first time logging in, log in with the default credentials shown.

By default, an R2R instance is hosted on port 7272. The login page will include this URL by default, but be sure to update the URL if your R2R instance is deployed elsewhere. For information about deploying a local R2R application server, see the [quickstart](/documentation/quickstart).

![R2R Dashboard Overview](/images/login.png)

### Documents

The documents page provides an overview of uploaded documents and their metadata. You can upload new documents and update, download, or delete existing ones. Additionally, you can view information about each document, including the documents' chunks and previews of PDFs.

![Documents Page](/images/oss_dashboard_documents.png)

### Collections

Collections allow users to create and share sets of documents. The collections page provides a place to manage your existing collections or create new collections.

![Collections Page](/images/oss_collections_page.png)

### Chat

In the chat page, you can stream RAG responses with different models and configurable settings. You can interact with both the RAG Agent and RAG endpoints here.

![Chat Interface](/images/chat.png)

### Users

Manage your users and gain insight into their interactions.

![Users Page](/images/users.png)

### Logs

The Logs page enables tracking of user queries, search results, and LLM responses.

![Logs Page](/images/logs.png)

### Settings

The settings page allows you to view the configuration of and edit the prompts associated with your R2R deployment.

![Logs Page](/images/settings_config.png)
![Logs Page](/images/settings_prompts.png)

## Development

To develop the R2R dashboard:

1. Start the development server:

```zsh
pnpm dev
```

2. Run pre-commit checks (optional but recommended):

```zsh
pnpm format
pnpm lint
```
