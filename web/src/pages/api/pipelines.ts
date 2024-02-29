import { NextApiRequest, NextApiResponse } from 'next';

const pipelines = [
  {
    id: 1,
    name: 'sciphi-r2r',
    deployment_url: 'https://github.com/SciPhi-AI/agent-search',
    last_commit_name: 'update home',
    logo: 'sciphi.png',
    updated_at: {
      when: '12/26/21',
      from_other_services: true,
      service: 'github',
    },
  },
];

// eslint-disable-next-line import/no-anonymous-default-export
export default async (_: NextApiRequest, res: NextApiResponse) => {
  try {
    // console.log(pipelines);

    res.status(200).json(pipelines);
  } catch (error) {
    res.status(400).json({ message: 'Something went wrong' });
  }
};
