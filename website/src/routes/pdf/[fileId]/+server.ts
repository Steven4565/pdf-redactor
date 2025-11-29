import fs from 'fs';
import path from 'path';
import type { RequestHandler } from './$types';
import db from '$lib/db/db';

const UPLOAD_DIR = '~/Documents/work/kolosal/pdf-redactor/files/raw/'; // TODO: 

export const GET: RequestHandler = async ({ params, cookies }) => {
  const fileId = params.fileId;

  const anonUserId = cookies.get('anon_user_id');
  if (!anonUserId) return new Response('Unauthorized', { status: 401 });

  const file = db
    .prepare('SELECT stored_name, owner_token FROM files WHERE id = ?')
    .get(fileId) as { stored_name: string; owner_token: string } | undefined;
  if (!file) return new Response('Not found', { status: 404 });

  if (file.owner_token !== anonUserId) return new Response('Not found', { status: 404 });

  const filePath = path.join(UPLOAD_DIR, file.stored_name);
  if (!fs.existsSync(filePath)) return new Response('Not found', { status: 404 });

  const data = await fs.promises.readFile(filePath);

  return new Response(data, {
    headers: {
      'Content-Type': 'application/pdf',
      'Cache-Control': 'private, max-age=0, must-revalidate'
    }
  });
};
