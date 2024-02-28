// pages/api/getSecrets.ts
import { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  try {
    // Update this URL to the endpoint that fetches all secrets without filtering by provider ID
    const response = await fetch('http://127.0.0.1:8000/get_secrets');
    if (!response.ok) {
      throw new Error('Failed to fetch secrets');
    }
    const secrets = await response.json();
    res.status(200).json(secrets);
  } catch (error) {
    console.error('Error fetching secrets:', error);
    res.status(500).json({ message: 'Internal Server Error' });
  }
}
