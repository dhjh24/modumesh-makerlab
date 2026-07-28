import type { NextApiRequest, NextApiResponse } from 'next';

type HealthResponse = {
  status: string;
  service: string;
  timestamp: string;
};

export default function handler(req: NextApiRequest, res: NextApiResponse<HealthResponse>) {
  res.status(200).json({
    status: 'ok',
    service: 'modumesh-web',
    timestamp: new Date().toISOString(),
  });
}
