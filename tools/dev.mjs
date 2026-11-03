// Optional preview entry point. Normal local use is simply `python run.py`.
import { spawn } from 'node:child_process';
import { resolve } from 'node:path';
const python = process.env.BLINDSPOT_PYTHON || (process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python');
const portArg = process.argv.indexOf('--port');
const port = portArg >= 0 ? process.argv[portArg+1] : process.env.PORT || '3000';
const child = spawn(resolve(python), ['run.py', '--host', '0.0.0.0', '--port', port], {stdio:'inherit'});
child.on('error', error => { console.error('Create the Python virtual environment and install requirements first.', error.message); process.exit(1); });
child.on('exit', code => process.exit(code ?? 0));
for (const signal of ['SIGINT','SIGTERM']) process.on(signal,()=>child.kill(signal));
