import { access, readFile } from 'node:fs/promises';
import path from 'node:path';

const root = process.cwd();
const dist = path.join(root, 'dist');
const requiredFiles = [
  'index.html',
  '_redirects',
  '_headers',
  'favicon.svg',
  'pesaguard-logo.svg',
  'pesaguard-mark.svg',
];

for (const file of requiredFiles) {
  try {
    await access(path.join(dist, file));
  } catch {
    console.error(`Cloudflare Pages build check failed: dist/${file} is missing.`);
    process.exit(1);
  }
}

const html = await readFile(path.join(dist, 'index.html'), 'utf8');
const redirects = await readFile(path.join(dist, '_redirects'), 'utf8');
const headers = await readFile(path.join(dist, '_headers'), 'utf8');

if (!html.includes('<div id="root"></div>') || !html.includes('/assets/')) {
  console.error('Cloudflare Pages build check failed: built index.html is missing the app root or bundled assets.');
  process.exit(1);
}

if (!/^\/\*\s+\/index\.html\s+200\s*$/m.test(redirects)) {
  console.error('Cloudflare Pages build check failed: SPA fallback route is missing.');
  process.exit(1);
}

for (const header of ['X-Content-Type-Options: nosniff', 'Referrer-Policy:', 'X-Frame-Options: DENY']) {
  if (!headers.includes(header)) {
    console.error(`Cloudflare Pages build check failed: expected security header "${header}" is missing.`);
    process.exit(1);
  }
}

console.log('Cloudflare Pages build verified: app bundle, public brand assets, SPA fallback, and security headers are present.');
