from contextlib import asynccontextmanager
import asyncio
import json
from urllib.parse import urlparse
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ConfigDict
from .config import load_settings, ROOT
from .meta import MetaClient
from .perturbations import catalog
from .runner import Runner, public_experiment
from .storage import Store
from .prompts import PROMPT_VERSION
from .excel_export import xlsx_bytes
from .study_dashboard import from_experiments
import os
from pathlib import Path


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    problem_id: str
    cell_ids: list[str] | None = Field(default=None, min_length=1, max_length=100)
    trials: int | None = Field(default=None, ge=1, le=30)
    temperature: float | None = Field(default=None, ge=0, le=2)
    fresh: bool = False


def create_app(settings=None):
    settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app):
        data = await asyncio.to_thread(catalog, settings.bank_path)
        store = Store(settings.db_path)
        store.recover()
        runner = Runner(settings, data, store, MetaClient(settings))
        app.state.runner, app.state.data = runner, data
        if settings.mode == "mock" and settings.seed_demo:
            example = runner.create('gaussian' if any(p['id']=='gaussian' for p in data['problems']) else data['problems'][0]['id'])
            if example["status"] != "complete":
                await runner.run(example["id"], fast=True)
        yield
        await runner.shutdown()

    app = FastAPI(title="Blindspot", version="1.0.0", lifespan=lifespan)

    @app.middleware("http")
    async def same_origin(request: Request, call_next):
        origin = request.headers.get("origin")
        if request.method == "POST" and origin and urlparse(origin).netloc != request.headers.get("host"):
            return JSONResponse({"detail": "Cross-origin experiment requests are not allowed."}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'self'"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/")
    def index():
        return FileResponse(ROOT / "static" / "index.html")

    @app.get('/research/{name}')
    def research_document(name: str):
        # A small explicit allowlist keeps local settings/runtime files private.
        allowed={'README.md':ROOT/'README.md','FINAL_FINDINGS.md':ROOT/'FINAL_FINDINGS.md',
                 'REPRODUCIBILITY.md':ROOT/'REPRODUCIBILITY.md',
                 'COST_SUMMARY.md':ROOT/'docs/public-cost-summary.md'}
        if name not in allowed or not allowed[name].is_file():
            raise HTTPException(404,'Research document not found')
        return FileResponse(allowed[name],media_type='text/plain; charset=utf-8')

    @app.get("/api/health")
    def health():
        return {"status": "ok", "mode": settings.mode, "dataset_problems": len(app.state.data["problems"])}

    @app.get("/api/catalog")
    def get_catalog():
        return {"settings": settings.public(), "dataset": app.state.data}

    @app.get('/api/representation')
    def representation_study():
        experiments=[e for e in app.state.runner.store.all() if e.get('basis_study')
            and e['config']['mode']==settings.mode and e['cache_identity']['account']==settings.namespace
            and e['dataset_hash']==app.state.data['hash']]
        current=from_experiments(experiments)
        pilot_path=ROOT/'data'/'matrix-focus-pilot.json'
        pilot=json.loads(pilot_path.read_text(encoding='utf-8')) if pilot_path.exists() else None
        completed_path=ROOT/'data'/'basis-study-results.json'
        completed=json.loads(completed_path.read_text(encoding='utf-8')) if completed_path.exists() else None
        return dict(current=current,pilot=pilot,completed=completed)

    @app.get('/api/final-study')
    def final_study():
        local=Path(os.getenv('BLINDSPOT_FINAL_DIRECTORY',str(ROOT/'var'/'final-study')))
        path=local/'dashboard.json'
        if not path.exists():path=ROOT/'data'/'final-panel-results.json'
        if not path.exists():path=ROOT/'data'/'final-panel-public.json'
        return json.loads(path.read_text(encoding='utf-8')) if path.exists() else dict(mode='pending',models=[],prediction_status='pending_or_incomplete')

    def lookup(experiment_id):
        e = app.state.runner.store.get(experiment_id)
        if not e or e["config"]["mode"] != settings.mode:
            raise HTTPException(404, "Experiment not found in the current mode")
        if e["cache_identity"]["account"] != settings.namespace:
            raise HTTPException(404, "Experiment not found for this API configuration")
        return e

    @app.get("/api/experiments")
    def history(problem_id: str | None = None):
        items = app.state.runner.store.all()
        return [{k: e[k] for k in ["id", "problem_id", "status", "config", "created_at", "updated_at", "cell_ids", "batch"]}
                for e in items if e["config"]["mode"] == settings.mode and e["cache_identity"]["account"] == settings.namespace
                and e["dataset_hash"] == app.state.data["hash"]
                and (problem_id is None or e["problem_id"] == problem_id)]

    @app.post("/api/experiments")
    async def create_experiment(body: RunRequest):
        runner = app.state.runner
        # Keep one foreground experiment per process; avoids accidental duplicate spending.
        active = [i for i, task in runner.tasks.items() if not task.done()]
        if active:
            raise HTTPException(409, f"Experiment {active[0]} is still running. Pause it or wait for completion.")
        try:
            e = runner.create(**body.model_dump())
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        if e["status"] != "complete":
            runner.start(e["id"])
        return public_experiment(e)

    @app.get("/api/experiments/{experiment_id}")
    def get_experiment(experiment_id: str):
        return public_experiment(lookup(experiment_id))

    @app.post("/api/experiments/{experiment_id}/resume")
    async def resume(experiment_id: str):
        e = lookup(experiment_id)
        if e.get('search_stage'):
            raise HTTPException(409, 'Imported search records are frozen. Resume the search CLI or create a fresh app experiment.')
        if e["dataset_hash"] != app.state.data["hash"] or e["prompt_version"] != PROMPT_VERSION or e["config"] != {**settings.public(), "trials": e["config"]["trials"], "temperature": e["config"]["temperature"]}:
            raise HTTPException(409, "Dataset or model settings changed. Create a new experiment.")
        active = [i for i,t in app.state.runner.tasks.items() if not t.done() and i != experiment_id]
        if active:
            raise HTTPException(409, "Another experiment is running.")
        app.state.runner.start(experiment_id)
        return public_experiment(e)

    @app.post("/api/experiments/{experiment_id}/pause")
    async def pause(experiment_id: str):
        lookup(experiment_id)
        app.state.runner.cancelled.add(experiment_id)
        return {"status": "pausing", "message": "In-flight requests finish and are saved. No new calls will start."}

    @app.get("/api/experiments/{experiment_id}/export")
    def export(experiment_id: str):
        e = lookup(experiment_id)
        problem = e["problem_snapshot"]
        payload = {"experiment": public_experiment(e, include_raw=True), "problem": problem,
                   "warning": "SIMULATED DATA: no Meta API calls were made." if settings.mode == "mock" else "Live results. Unusable responses are excluded and must be reported."}
        return Response(json.dumps(payload, indent=2, ensure_ascii=False), media_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="blindspot-{settings.mode}-{experiment_id[:8]}.json"'})

    @app.get("/api/experiments/{experiment_id}/export.xlsx")
    def export_excel(experiment_id: str):
        e=lookup(experiment_id)
        content=xlsx_bytes({'experiment':public_experiment(e,include_raw=True),'problem':e['problem_snapshot']})
        return Response(content,media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                        headers={'Content-Disposition':f'attachment; filename="blindspot-{settings.mode}-{experiment_id[:8]}.xlsx"'})

    app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
    return app


app = create_app()
