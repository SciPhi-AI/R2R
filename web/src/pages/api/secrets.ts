import { NextApiRequest, NextApiResponse } from 'next';

// Mock database for secrets
let secretsDB = [];

export default function handler(req: NextApiRequest, res: NextApiResponse) {
  const { provider, secretName } = req.query;

  switch (req.method) {
    case 'GET':
      // Handle GET request
      const secrets = secretsDB.filter(
        (secret) => secret.provider === provider && secret.name === secretName
      );
      res.status(200).json({ secrets });
      break;
    case 'POST':
      // Handle POST request
      const newSecret = JSON.parse(req.body);
      secretsDB.push(newSecret);
      res.status(201).json({ message: 'Secret created', secret: newSecret });
      break;
    case 'DELETE':
      // Handle DELETE request
      secretsDB = secretsDB.filter(
        (secret) =>
          !(secret.provider === provider && secret.name === secretName)
      );
      res.status(200).json({ message: 'Secret deleted' });
      break;
    default:
      res.setHeader('Allow', ['GET', 'POST', 'DELETE']);
      res.status(405).end(`Method ${req.method} Not Allowed`);
  }
}
