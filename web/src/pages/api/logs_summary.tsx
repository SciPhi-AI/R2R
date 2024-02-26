import { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  try {
    const response = await fetch('http://127.0.0.1:8000/logs_summary');
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
