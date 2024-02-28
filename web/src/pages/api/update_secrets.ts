import { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  if (req.method !== 'POST') {
    return res.status(405).json({ message: 'Method Not Allowed' });
  }

  const updatedSecrets = req.body; // Assuming this is the updated secrets data

  try {
    // Fetch existing secrets
    const existingSecrets = await fetchExistingSecrets();

    // Validate merged secrets
    const isValid = validateSecretsLength(updatedSecrets, existingSecrets);
    if (!isValid) {
      return res
        .status(400)
        .json({
          message:
            'Validation failed: Secrets do not match the required length.',
        });
    }

    // Merge existing secrets with updated data
    const mergedSecrets = { ...existingSecrets, ...updatedSecrets };

    // Update the secrets in the database or via an external service
    await updateSecretsInDatabase(mergedSecrets);

    res.status(200).json({ message: 'Secrets updated successfully' });
  } catch (error) {
    console.error('Error updating secrets:', error);
    res.status(500).json({ message: 'Internal Server Error' });
  }
}

// Placeholder for fetching existing secrets
async function fetchExistingSecrets() {
  // Implement fetching logic here, possibly reusing logic from get_secrets.ts
  const response = await fetch('http://127.0.0.1:8000/get_secrets');
  if (!response.ok) {
    throw new Error('Failed to fetch existing secrets');
  }
  return response.json();
}

// Placeholder for updating secrets in the database
async function updateSecretsInDatabase(secrets: any) {
  // Implement update logic here
}

// New function to validate the length of updated secrets against existing ones
function validateSecretsLength(
  updatedSecrets: any,
  existingSecrets: any
): boolean {
  for (const key in updatedSecrets) {
    if (
      existingSecrets.hasOwnProperty(key) &&
      updatedSecrets[key].length !== existingSecrets[key].length
    ) {
      return false; // Validation fails if any updated secret does not match the length of its counterpart
    }
  }
  return true; // Validation passes
}
