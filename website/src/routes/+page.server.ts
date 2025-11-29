import { fail } from '@sveltejs/kit';
import { writeFile, mkdir } from 'fs/promises';
import { existsSync } from 'fs';
import { join } from 'path';
import { randomBytes } from 'crypto';
import type { Actions } from "./$types"
import db from '$lib/db/db'

const PYTHON_API_URL = 'http://localhost:8000/';
const UPLOAD_DIR = join(process.cwd(), 'files/raw');

const insertFile = db.prepare(`
  INSERT INTO files (id, original_name, stored_name, owner_token)
  VALUES (?, ?, ?, ?)
`);

function generateId(length = 16): string {
  return randomBytes(length).toString('hex');
}

function getOrCreateAnonUserId(cookies: any): string {
  let anonUserId = cookies.get('anon_user_id');
  // TODO: maybe set this to expire

  if (!anonUserId) {
    anonUserId = generateId(32);
    cookies.set('anon_user_id', anonUserId, {
      path: '/',
      httpOnly: true,
      secure: true,
      sameSite: 'strict',
      maxAge: 60 * 60 * 24 * 365 // 1 year
    });
  }

  return anonUserId;
}

export const actions: Actions = {
  default: async ({ request, cookies }) => {
    try {
      const formData = await request.formData();
      const files = formData.getAll('files') as File[];
      const categories = JSON.parse(
        (formData.get('categories') as string) || '[]'
      );

      if (files.length === 0) {
        return fail(400, { error: 'No files uploaded' });
      }

      const anonUserId = getOrCreateAnonUserId(cookies);

      if (!existsSync(UPLOAD_DIR)) {
        await mkdir(UPLOAD_DIR, { recursive: true });
      }

      const uploadedFiles: Array<{
        fileId: string;
        fileName: string;
        storedName: string;
        filePath: string;
      }> = [];

      for (const file of files) {
        if (file.size === 0) continue;

        const fileId = generateId(16);
        const ext = file.name.split('.').pop();
        const storedName = `${fileId}.${ext}`;
        const filePath = join(UPLOAD_DIR, storedName);

        const buffer = Buffer.from(await file.arrayBuffer());
        await writeFile(filePath, buffer);

        insertFile.run(fileId, file.name, storedName, anonUserId);

        uploadedFiles.push({
          fileId,
          fileName: file.name,
          storedName,
          filePath
        });
      }

      const pythonFormData = new FormData();

      uploadedFiles.forEach((f) => {
        pythonFormData.append('file_paths', f.filePath);
        pythonFormData.append('file_ids', f.fileId);
      });

      pythonFormData.append('categories', JSON.stringify(categories));
      pythonFormData.append('owner_token', anonUserId);

      const res = await fetch(`${PYTHON_API_URL}redact/`, {
        method: 'POST',
        body: pythonFormData
      });

      if (!res.ok) {
        return fail(res.status, {
          error: `Python server error: ${res.status}`
        });
      }

      const result = await res.json();

      if (!result?.job_id) {
        return fail(500, { error: 'No job_id returned from server' });
      }

      return {
        success: true,
        job_id: result.job_id,
        status: result.status
      };
    } catch (err: any) {
      console.error('Upload error:', err);
      return fail(500, { error: err?.message ?? 'Upload failed' });
    }
  }
};
