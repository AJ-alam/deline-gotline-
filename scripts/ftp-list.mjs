// Quick FTP directory explorer — lists paths given as args (default "/")
import { Client } from 'basic-ftp';

const get = (n) => process.env[n];
const client = new Client(30_000);
try {
  await client.access({
    host: get('HOSTINGER_FTP_HOST'),
    user: get('HOSTINGER_FTP_USER'),
    password: get('HOSTINGER_FTP_PASS'),
    secure: true,
    secureOptions: { rejectUnauthorized: false },
  });
  const paths = process.argv.slice(2).length ? process.argv.slice(2) : ['/'];
  for (const p of paths) {
    console.log(`\n== ${p} ==`);
    const list = await client.list(p);
    for (const f of list) console.log(`${f.isDirectory ? 'd' : '-'} ${f.name}`);
  }
} catch (err) {
  console.error('FTP error:', err.message);
  process.exitCode = 1;
} finally {
  client.close();
}
