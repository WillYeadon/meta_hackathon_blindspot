import asyncio
import copy
from dataclasses import replace
import hashlib
import json
import uuid
from .meta import build_request, ModelError, utcnow
from .metrics import aggregate
from .prompts import search_messages, PROMPT_VERSION


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class Runner:
    def __init__(self, settings, catalog, store, client):
        self.settings, self.catalog, self.store, self.client = settings, catalog, store, client
        self.tasks, self.cancelled, self.call_locks = {}, set(), {}
        self.limit = asyncio.Semaphore(settings.concurrency)

    def save(self, experiment):
        experiment["updated_at"] = utcnow()
        self.store.save(experiment)

    def create(self, problem_id, cell_ids=None, trials=None, temperature=None, fresh=False):
        problem = next((p for p in self.catalog["problems"] if p["id"] == problem_id), None)
        if not problem:
            raise ValueError("Unknown problem")
        selected = cell_ids or [c["id"] for c in problem["cells"]]
        if not selected or len(set(selected)) != len(selected) or not set(selected) <= {c["id"] for c in problem["cells"]}:
            raise ValueError("Unknown or duplicate cell")
        trials = trials if trials is not None else self.settings.trials
        temperature = temperature if temperature is not None else self.settings.temperature
        batch = str(uuid.uuid4()) if fresh else "baseline"
        config = {**self.settings.public(), "trials": trials, "temperature": temperature}
        cache_identity = dict(config=config, dataset=self.catalog["hash"], prompts=PROMPT_VERSION,
                              account=self.settings.namespace, batch=batch)
        protocol = problem.get("verifier_protocol", "legacy")
        if protocol != "legacy":
            cache_identity["verifier_protocol"] = protocol
        signature = digest({**cache_identity, "cells": sorted(selected)})
        if existing := self.store.get(signature=signature):
            return existing
        experiment = dict(id=str(uuid.uuid4()), signature=signature, problem_id=problem_id, cell_ids=selected,
                          problem_snapshot=copy.deepcopy(problem),
                          cache_identity=cache_identity, config=config, dataset_hash=self.catalog["hash"],
                          prompt_version=PROMPT_VERSION, batch=batch, status="queued", phase="parsed",
                          verifier_protocol=protocol,
                          created_at=utcnow(), updated_at=utcnow(), results={}, events=[],
                          completed_calls=0, cached_calls=0, total_calls=len(selected)*(trials+int(problem.get('collect_forecasts',True))),
                          forecasts_expected=problem.get('collect_forecasts',True), error=None)
        self.save(experiment)
        return experiment

    def start(self, experiment_id, fast=False):
        if experiment_id not in self.tasks or self.tasks[experiment_id].done():
            self.cancelled.discard(experiment_id)
            self.tasks[experiment_id] = asyncio.create_task(self.run(experiment_id, fast))

    def event(self, experiment, kind, cell_id=None, ordinal=None):
        experiment["events"].append(dict(sequence=len(experiment["events"])+1, at=utcnow(), kind=kind,
                                         cell_id=cell_id, ordinal=ordinal))

    async def obtain(self, experiment, cell, messages, prediction, ordinal, fast):
        request = build_request(self.settings, messages, prediction, experiment["config"]["temperature"])
        key = digest(dict(identity=experiment["cache_identity"], cell=cell["id"], request=request,
                          kind="prediction" if prediction else "trial", ordinal=ordinal))
        # Same ordinal cannot become multiple paid calls if concurrent runs share a cell.
        lock = self.call_locks.setdefault(key, asyncio.Lock())
        async with lock:
            if existing := self.store.call(key):
                experiment["cached_calls"] += 1
                return {**existing, "cached": True}
            async with self.limit:
                if experiment["id"] in self.cancelled:
                    raise asyncio.CancelledError
                self.event(experiment, "prediction_started" if prediction else "trial_started", cell["id"], ordinal)
                self.save(experiment)
                try:
                    result = await self.client.complete(request, cell=cell, ordinal=ordinal, fast=fast)
                    result.update(status="ok", mode=self.settings.mode, request=request, ordinal=ordinal)
                    self.store.save_call(key, result)
                    return {**result, "cached": False}
                except ModelError as exc:
                    return dict(status="error", error=str(exc), raw_response=exc.raw, request=request,
                                ordinal=ordinal, completed_at=utcnow(), mode=self.settings.mode, cached=False)

    async def run(self, experiment_id, fast=False):
        e = self.store.get(experiment_id)
        if e["status"] == "complete":
            return e
        problem = next(p for p in self.catalog["problems"] if p["id"] == e["problem_id"])
        cells = [c for c in problem["cells"] if c["id"] in e["cell_ids"]]
        prompt_settings = replace(self.settings, temperature=e["config"]["temperature"])
        protocol = e.get("verifier_protocol", "legacy")
        e.update(status="running", phase="predictions", error=None, completed_calls=0, cached_calls=0)
        self.event(e, "validated")
        self.save(e)

        async def predict(cell):
            result = await self.obtain(e, cell, search_messages(problem, cell, e["config"]["trials"], prompt_settings, True, protocol, protocol != "legacy"), True, 0, fast)
            e["results"][cell["id"]] = {"prediction": result, "trials": [], "metrics": {}}
            e["completed_calls"] += 1
            self.event(e, "prediction_saved", cell["id"])
            self.save(e)

        async def verify(cell, ordinal):
            result = await self.obtain(e, cell, search_messages(problem, cell, e["config"]["trials"], prompt_settings, False, protocol), False, ordinal, fast)
            record = e["results"][cell["id"]]
            record["trials"].append(result)
            record["trials"].sort(key=lambda t: t["ordinal"])
            record["metrics"] = aggregate(record, cell["is_control"])
            e["completed_calls"] += 1
            self.event(e, "trial_saved", cell["id"], ordinal)
            self.save(e)

        async def phase(coroutines):
            # Wait for all in-flight work to settle on pause. A sibling must not
            # continue writing after the experiment has been marked cancelled.
            outcomes = await asyncio.gather(*coroutines, return_exceptions=True)
            for outcome in outcomes:
                if isinstance(outcome, BaseException):
                    raise outcome

        try:
            # Global phase barrier: every forecast is durable before ANY empirical call.
            if e.get('forecasts_expected',True):
                await phase([predict(c) for c in cells])
            else:
                e['results']={c['id']:dict(prediction=None,trials=[],metrics={}) for c in cells}
            failed = [r["prediction"] for r in e["results"].values() if r["prediction"] and r["prediction"]["status"] != "ok"]
            if failed:
                e.update(status="failed", phase="predictions", error="No trials started because a self-prediction failed. " + failed[0]["error"])
                return e
            if experiment_id in self.cancelled:
                raise asyncio.CancelledError
            self.event(e, "all_predictions_saved")
            e["phase"] = "trials"
            self.save(e)
            await phase([verify(c, i) for c in cells for i in range(e["config"]["trials"])])
            failures = sum(r["metrics"]["failed_trials"] for r in e["results"].values())
            e.update(status="partial" if failures else "complete", phase="complete",
                     error=f"{failures} unusable trial(s); excluded from the denominator. Resume to retry only failed slots." if failures else None)
            self.event(e, "map_completed")
        except asyncio.CancelledError:
            e.update(status="cancelled", phase="cancelled", error="Paused. Completed calls are saved; resume to continue.")
        except Exception as exc:
            e.update(status="failed", error=f"Experiment failed ({type(exc).__name__}). See server logs.")
            import logging
            logging.exception("Experiment runner failed")
        finally:
            self.save(e)
        return e

    async def shutdown(self):
        self.cancelled.update(self.tasks)
        active = [t for t in self.tasks.values() if not t.done()]
        for task in active:
            task.cancel()
        await asyncio.gather(*active, return_exceptions=True)
        await self.client.close()


def public_experiment(experiment, include_raw=False):
    if not experiment:
        return None
    result = copy.deepcopy(experiment)
    result.pop("cache_identity", None)
    result.pop("signature", None)
    result.pop("problem_snapshot", None)
    if not include_raw:
        for cell in result["results"].values():
            for call in [cell.get("prediction")] + cell.get("trials", []):
                if call:
                    call.pop("request", None)
                    call.pop("raw_response", None)
    return result
