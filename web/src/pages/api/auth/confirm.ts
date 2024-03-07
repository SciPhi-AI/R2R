import { NextApiRequest, NextApiResponse } from 'next';
import createClient from '@/utils/supabase/api';

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {

  const { token_hash, next, email } = req.query;

  if (!token_hash) {
    // console.log('Token hash is missing');
    res.status(400).json({ error: 'Token hash is missing' });
    return;
  }


  res.redirect(
    307,
    `/update_password?token_hash=${token_hash}&email=${email}&next=${next || '/'}`
  );
}
