import Database from 'better-sqlite3';
import { mkdir } from 'fs/promises';
import { existsSync } from 'fs';

const DB_DIR = '~/Documents/work/kolosal/pdf-redactor/frontend/db/'
if (!existsSync(DB_DIR)) {
  await mkdir(DB_DIR, { recursive: true });
}
const db = new Database(`${DB_DIR}data.db`);

db.exec(`
  CREATE TABLE IF NOT EXISTS files (
    id TEXT PRIMARY KEY,
    owner_token TEXT NOT NULL,
    stored_name TEXT NOT NULL,
    original_name TEXT
  );
`);

// console.log("finished executing")
