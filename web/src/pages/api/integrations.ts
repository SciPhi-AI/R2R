import { NextApiRequest, NextApiResponse } from 'next';

const availableIntegrations = [
  // data providers
  // {
  //   id: 1,
  //   name: "Postgres",
  //   type:"dataset-provider",
  //   logo: "postgres.png"
  // },
  {
    id: 2,
    name: 'Amazon S3',
    type: 'dataset-provider',
    logo: 'amazon-s3.svg',
  },
  {
    id: 3,
    name: 'Google Cloud',
    type: 'dataset-provider',
    logo: 'gcloud.png',
  },
  {
    id: 4,
    name: 'HuggingFace',
    type: 'dataset-provider',
    logo: 'hf2.png',
  },
  // vector dbs
  {
    id: 1,
    name: 'Postgres',
    type: 'vector-db-provider',
    logo: 'postgres.png',
  },
  {
    id: 2,
    name: 'Qdrant',
    type: 'vector-db-provider',
    logo: 'qdrant.png',
  },
  {
    id: 3,
    name: 'Chroma',
    type: 'vector-db-provider',
    logo: 'chroma.png',
  },
  {
    id: 4,
    name: 'Weaviate',
    type: 'vector-db-provider',
    logo: 'weaviate.png',
  },
  {
    id: 5,
    name: 'Pinecone',
    type: 'vector-db-provider',
    logo: 'pinecone.png',
  },
  // integrations
  {
    id: 1,
    name: 'Bing',
    type: 'integration',
    logo: 'bing.png',
  },
  {
    id: 2,
    name: 'Serper',
    type: 'integration',
    logo: 'serper.jpeg',
  },
  {
    id: 3,
    name: 'AgentSearch',
    type: 'integration',
    logo: 'sciphi.png',
  },

  // LLM Providers
  {
    id: 1,
    name: 'OpenAI',
    type: 'llm_provider',
    logo: 'openai.png',
  },
  {
    id: 1,
    name: 'Anthropic',
    type: 'llm_provider',
    logo: 'anthropic.jpeg',
  },
  {
    id: 2,
    name: 'Cohere',
    type: 'llm_provider',
    logo: 'cohere2.png',
  },
  {
    id: 3,
    name: 'Google',
    type: 'llm_provider',
    logo: 'google.jpeg',
  },
  {
    id: 4,
    name: 'HuggingFace',
    type: 'llm_provider',
    logo: 'hf2.png',
  },
];

// eslint-disable-next-line import/no-anonymous-default-export
export default async (_: NextApiRequest, res: NextApiResponse) => {
  try {
    // console.log(availableIntegrations);

    res.status(200).json(availableIntegrations);
  } catch (error) {
    res.status(400).json({ message: 'Something went wrong' });
  }
};
