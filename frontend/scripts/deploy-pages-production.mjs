import { spawn, spawnSync } from 'node:child_process';

const expectedApiOrigin = 'https://api.datasource.pesaguard.co.ke';
const rawApiBase = process.env.VITE_API_BASE_URL?.trim();

if (!rawApiBase) {
  console.error('Refusing production deployment: set VITE_API_BASE_URL to the verified production API origin.');
  process.exit(1);
}

let apiUrl;
try {
  apiUrl = new URL(rawApiBase);
} catch {
  console.error('Refusing production deployment: VITE_API_BASE_URL must be an absolute URL.');
  process.exit(1);
}

if (
  apiUrl.origin !== expectedApiOrigin ||
  apiUrl.pathname !== '/' ||
  apiUrl.search ||
  apiUrl.hash ||
  apiUrl.username ||
  apiUrl.password
) {
  console.error(`Refusing production deployment: VITE_API_BASE_URL must be exactly ${expectedApiOrigin}.`);
  process.exit(1);
}

const build = spawnSync('npm', ['run', 'pages:build'], {
  cwd: process.cwd(),
  stdio: 'inherit',
  shell: process.platform === 'win32',
});
if (build.error) {
  console.error('Unable to start frontend build:', build.error.message);
  process.exit(1);
}
if (build.status !== 0) {
  console.error('Production deployment stopped because the frontend build or Pages verification failed.');
  process.exit(build.status ?? 1);
}

const args = [
  '--yes',
  'wrangler',
  'pages',
  'deploy',
  'dist',
  '--config',
  'wrangler.production.jsonc',
  '--project-name=pesaguard-datasource-web',
  '--branch=main',
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
