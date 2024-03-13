import { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  try {
    // Extract the pipelineId from the query parameters
    const { pipelineId } = req.query;

    // Construct the URL with the pipelineId
    const externalServiceUrl = `https://external-service.com/logs_summary?pipelineId=${pipelineId}`;

    // Fetch the logs summary from the constructed URL
    const response = await fetch(externalServiceUrl);
    if (!response.ok) {
      throw new Error('Failed to fetch logs summary from the external source');
    }
    const data = await response.json();
    res.status(200).json(data);
  } catch (error) {
    console.error('Error fetching logs:', error);
    res.status(500).json({ message: 'Internal Server Error' });
  }
}
