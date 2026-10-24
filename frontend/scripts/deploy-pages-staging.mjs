import { spawn } from 'node:child_process';

const rawApiBase = process.env.VITE_API_BASE_URL?.trim();
if (!rawApiBase) {
  console.error('Refusing staging deployment: set VITE_API_BASE_URL to the verified staging API origin.');
  process.exit(1);
}

let apiUrl;
try {
  apiUrl = new URL(rawApiBase);
} catch {
  console.error('Refusing staging deployment: VITE_API_BASE_URL must be a valid absolute URL.');
  process.exit(1);
}

if (
  apiUrl.protocol !== 'https:' ||
  apiUrl.username ||
  apiUrl.password ||
  apiUrl.search ||
  apiUrl.hash ||
  apiUrl.hostname === 'api.datasource.pesaguard.co.ke' ||
  apiUrl.hostname === 'api.pesaguard.co.ke' ||
  apiUrl.hostname.endsWith('.example.invalid') ||
  apiUrl.hostname === 'localhost' ||
  apiUrl.hostname === '127.0.0.1'
) {
  console.error('Refusing staging deployment: use a real HTTPS staging API origin, not production, localhost, or a placeholder.');
  process.exit(1);
}

const args = [
  '--yes',
  'wrangler',
  'pages',
  'deploy',
  'dist',
  '--config',
  'wrangler.jsonc',
  '--project-name=pesaguard-datasource-staging',
  '--branch=staging',
];

const child = spawn('npx', args, {
  cwd: process.cwd(),
  stdio: 'inherit',
  shell: process.platform === 'win32',
});

child.on('error', (error) => {
  console.error('Unable to start Wrangler:', error.message);
  process.exitCode = 1;
});
child.on('exit', (code, signal) => {
  if (signal) {
    console.error(`Wrangler exited due to signal: ${signal}`);
    process.exitCode = 1;
  } else {
    process.exitCode = code ?? 1;
  }
});
