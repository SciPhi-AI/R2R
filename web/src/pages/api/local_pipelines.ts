import { NextApiRequest, NextApiResponse } from 'next';
import { store } from '@/store'; 


export default async (req: NextApiRequest, res: NextApiResponse) => {
  try {
  
    // LocalMode
    await store.loadData(); // Ensure the store is loaded once for any local mode operation

    switch (req.method) {
      case 'POST':
        return handlePost(req, res);
      case 'GET':
        const pipelines = store.getAllPipelines();
        return res.status(200).json(pipelines);
      default:
        res.setHeader('Allow', ['GET', 'POST']);
        return res.status(405).end(`Method ${req.method} Not Allowed`);
    }
  } catch (error) {
    res.status(400).json({ message: 'Something went wrong' });
  }
};

async function handlePost(req: NextApiRequest, res: NextApiResponse) {
  const { id, pipeline } = req.body;
  if (!id || !pipeline) {
    return res.status(400).json({ message: 'Missing id or pipeline data' });
  }
  store.updatePipeline(id, pipeline);
  return res.status(200).json({ message: 'Pipeline updated successfully' });
}