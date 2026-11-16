// PM2 ecosystem for a single-server deployment.
//
// Assumes the repository is at /var/www/dossier and the commands are run as the
// `dossier` user. Adjust APP_DIR if your path differs.
//
//   pm2 startOrReload /var/www/dossier/deploy/ecosystem.config.cjs --update-env
//   pm2 save
//
// The Python processes use interpreter: "none" because they are real executables
// inside the project virtualenv, not JavaScript files.

const APP_DIR = "/var/www/dossier";

const pythonJob = (name, script, args, memory) => ({
  name,
  cwd: `${APP_DIR}/backend`,
  script,
  args,
  interpreter: "none",
  env: {
    PYTHONUNBUFFERED: "1",
  },
  autorestart: true,
  restart_delay: 3000,
  kill_timeout: 15000,
  max_memory_restart: memory,
  time: true,
});

module.exports = {
  apps: [
    pythonJob(
      "dossier-api",
      ".venv/bin/uvicorn",
      "app.main:app --host 127.0.0.1 --port 8000 --workers 2 " +
        "--proxy-headers --forwarded-allow-ips=127.0.0.1",
      "700M",
    ),
    pythonJob(
      "dossier-worker",
      ".venv/bin/celery",
      "-A app.workers.celery_app:celery_app worker --loglevel=INFO --concurrency=2",
      "1G",
    ),
    pythonJob(
      "dossier-beat",
      ".venv/bin/celery",
      "-A app.workers.celery_app:celery_app beat --loglevel=INFO " +
        `--pidfile=${APP_DIR}/backend/celerybeat.pid ` +
        `--schedule=${APP_DIR}/backend/celerybeat-schedule`,
      "256M",
    ),
    {
      name: "dossier-web",
      cwd: `${APP_DIR}/frontend`,
      // Run the Next.js binary directly so PM2 does not need a Node interpreter shim.
      script: "node_modules/next/dist/bin/next",
      args: "start -H 127.0.0.1 -p 3000",
      interpreter: "none",
      env: {
        NODE_ENV: "production",
      },
      autorestart: true,
      restart_delay: 3000,
      kill_timeout: 15000,
      max_memory_restart: "700M",
      time: true,
    },
  ],
};
