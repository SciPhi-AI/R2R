import { NextApiRequest, NextApiResponse } from 'next';

export default async (req: NextApiRequest, res: NextApiResponse) => {
  try {
    const { pipeline_name, repo_url } = req.body;

    // Extract the token from the Authorization header
    const token = req.headers.authorization?.split(' ')[1]; // Assumes "Bearer <token>"
    if (!token) {
      return res.status(401).json({ message: 'Authentication token is missing' });
    }

    const response = await fetch(`${process.env.REMOTE_SERVER_URL}/user_clone_build_deploy`, {
      method: 'POST',
      headers: new Headers({
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }),
      body: JSON.stringify({
        pipeline_name,
        repo_url,
      }),
    });

    if (!response.ok) {
      throw new Error(`Error: ${response.status}`);
    }

    const responseJson = await response.json();

    // If the token is valid, proceed to send the response
    res.status(200).json(responseJson);
  } catch (error) {
    res.status(400).json({ message: 'Something went wrong' });
  }
};