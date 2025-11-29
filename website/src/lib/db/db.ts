import Database from 'better-sqlite3';

const DB_DIR = '~/Documents/work/kolosal/pdf-redactor/frontend/db/'
const db = new Database(`${DB_DIR}data.db`);

export default db;
