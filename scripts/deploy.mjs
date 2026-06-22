// Deploys dist/ to Hostinger shared hosting over FTPS.
// Credentials come from environment variables only — never hardcode them here:
//   HOSTINGER_FTP_HOST  e.g. "ftp.dgg.nexauratechs.com" or the server IP from hPanel
//   HOSTINGER_FTP_USER  FTP account username from hPanel -> FTP Accounts
//   HOSTINGER_FTP_PASS  FTP account password
//   HOSTINGER_FTP_DIR   remote web root (default "/public_html")
import { Client } from 'basic-ftp';
import { existsSync } from 'node:fs';
import { resolve } from 'node:path';

const HOST = process.env.HOSTINGER_FTP_HOST;
const USER = process.env.HOSTINGER_FTP_USER;
const PASS = process.env.HOSTINGER_FTP_PASS;
const REMOTE_DIR = process.env.HOSTINGER_FTP_DIR || '/public_html';
const LOCAL_DIR = resolve(import.meta.dirname, '..', 'dist');

if (!HOST || !USER || !PASS) {
  console.error('Missing HOSTINGER_FTP_HOST / HOSTINGER_FTP_USER / HOSTINGER_FTP_PASS environment variables.');
  process.exit(1);
}
if (!existsSync(resolve(LOCAL_DIR, 'index.html'))) {
  console.error(`No build found at ${LOCAL_DIR} — run "npm run build" first.`);
  process.exit(1);
}

const client = new Client(30_000);
try {
  await client.access({ host: HOST, user: USER, password: PASS, secure: true, secureOptions: { rejectUnauthorized: false } });
  console.log(`Connected to ${HOST}, deploying to ${REMOTE_DIR} ...`);
  await client.ensureDir(REMOTE_DIR);
  // Remove stale hashed assets so old bundles don't accumulate
  await client.removeDir(`${REMOTE_DIR}/assets`).catch(() => {});
  await client.ensureDir(REMOTE_DIR);
  await client.uploadFromDir(LOCAL_DIR, REMOTE_DIR);
  console.log('Deploy complete. Verify .htaccess landed:', (await client.list(REMOTE_DIR)).some(f => f.name === '.htaccess') ? 'yes' : 'NO — upload it manually');
} catch (err) {
  console.error('Deploy failed:', err.message);
  process.exitCode = 1;
} finally {
  client.close();
}
