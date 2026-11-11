"""Transactional offline synchronization into the operational registry."""
from datetime import datetime, timezone
import hashlib
import json

from sqlalchemy import func, select

from .db_models import AuditEvent, Department, Driver, DutySlip, Vehicle, VehicleAssignment, VimsSource, VimsSyncRun
from .db_records import normalized
from .vims_schema import VimsBatch

ENTITIES = {"departments": Department, "vehicles": Vehicle, "drivers": Driver,
            "assignments": VehicleAssignment, "duty_slips": DutySlip}


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class VimsConflict(ValueError):
    """A valid document cannot be reconciled with the current database."""


def digest(batch):
    return hashlib.sha256(json.dumps(batch.model_dump(mode="json"), sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def run_result(run, source):
    return {"id": run.id, "source": source.name, "batch_id": run.batch_id, "checksum": run.checksum,
            "exported_at": utc(run.exported_at).isoformat(), "occurred_at": utc(run.occurred_at).isoformat(),
            "actor": run.actor, "status": run.status, "summary": run.summary, "error": run.error}


class VimsStore:
    def vims_sync(self, batch: VimsBatch, actor: str, *, preview=False, expected_revision=None):
        checksum = digest(batch)
        failure = None
        with self._lock as session:
            source = session.scalar(select(VimsSource).where(VimsSource.name == batch.source))
            revision = source.revision if source else 0
            previous = session.scalar(select(VimsSyncRun).where(
                VimsSyncRun.source_id == source.id, VimsSyncRun.batch_id == batch.batch_id,
                VimsSyncRun.status == "APPLIED")) if source else None
            if previous and previous.checksum == checksum:
                return run_result(previous, source) | {"status": "ALREADY_APPLIED", "base_revision": revision, "changes": []}
            # Source creation is also rolled back for a preview.
            outer = session.begin_nested() if preview else None
            if source is None:
                source = VimsSource(name=batch.source, revision=0)
                session.add(source)
                session.flush()
            savepoint = session.begin_nested()
            try:
                if previous:
                    raise VimsConflict("This batch_id was already applied with different contents; use a new batch_id")
                if not preview and expected_revision != revision:
                    raise VimsConflict("Source changed since preview. Preview the batch again before applying")
                if source.exported_at and batch.exported_at <= utc(source.exported_at):
                    raise VimsConflict("exported_at must be later than the last applied export")
                summary, changes = self._vims_apply(session, source, batch)
                if preview:
                    result = {"source": source.name, "batch_id": batch.batch_id, "checksum": checksum,
                              "status": "PREVIEW", "base_revision": revision, "summary": summary, "changes": changes}
                    savepoint.rollback()
                    outer.rollback()
                    return result
                source.revision = revision + 1
                source.exported_at = batch.exported_at
                session.flush()
                savepoint.commit()
            except VimsConflict as exc:
                savepoint.rollback()
                if preview:
                    outer.rollback()
                    raise
                failure = str(exc)
                summary, changes = {}, []
            run = VimsSyncRun(source_id=source.id, batch_id=batch.batch_id, checksum=checksum,
                exported_at=batch.exported_at, occurred_at=datetime.now(timezone.utc), actor=actor,
                status="FAILED" if failure else "APPLIED", summary=summary, changes=changes, error=failure)
            session.add(run)
            session.flush()
            session.add(AuditEvent(occurred_at=run.occurred_at, actor=actor, action="VIMS_SYNC_" + run.status,
                entity=f"vims_sync_runs:{run.id}", details={"source": source.name, "batch_id": batch.batch_id,
                    "checksum": checksum, "summary": summary, "error": failure}))
            result = run_result(run, source) | {"base_revision": source.revision, "changes": changes}
        if failure:
            raise VimsConflict(failure)
        return result

    def _vims_apply(self, session, source, batch):
        summary, changes = {}, []

        def reference(model, external_id):
            value = session.scalar(select(model).where(model.vims_source_id == source.id,
                                                       model.vims_external_id == external_id))
            if value is None:
                raise VimsConflict(f"Unknown {model.__tablename__} reference: {external_id}")
            return value

        for kind, model in ENTITIES.items():
            counts = {"created": 0, "linked": 0, "updated": 0, "unchanged": 0}
            summary[kind] = counts
            for record in getattr(batch, kind):
                after = record.model_dump(mode="json", exclude={"link_existing"})
                item = session.scalar(select(model).where(model.vims_source_id == source.id,
                    model.vims_external_id == record.external_id))
                operation = "updated" if item else "created"
                # Identity matching is explicit; another source's records cannot be claimed.
                candidate = None
                if model is Department:
                    candidate = session.scalar(select(model).where(model.name == record.name))
                elif model is Vehicle:
                    candidate = session.scalar(select(model).where(model.normalized_plate == normalized(record.plate_number)))
                if candidate is not None and (item is None or candidate.id != item.id):
                    if item is not None or candidate.vims_source_id is not None:
                        raise VimsConflict(f"{kind}/{record.external_id}: identity already belongs to another record")
                    if not record.link_existing:
                        raise VimsConflict(f"{kind}/{record.external_id}: local record exists; set link_existing=true to adopt it")
                    item, operation = candidate, "linked"
                before = item.vims_payload if item else None
                if operation == "linked":
                    if model is Department:
                        before = {"name": item.name, "active": item.active}
                    else:
                        dept = session.get(Department, item.department_id) if item.department_id else None
                        before = dict(item.payload) | {"active": item.active, "authorized_areas": item.authorized_areas,
                            "department_external_id": (dept.vims_external_id or f"local:{dept.id}") if dept else None}
                if before == after:
                    counts["unchanged"] += 1
                    continue
                if item is None:
                    item = model()
                    session.add(item)
                with session.no_autoflush:
                    if model is Department:
                        item.name, item.active = record.name, record.active
                    elif model is Vehicle:
                        dept = reference(Department, record.department_external_id)
                        item.department_id = dept.id
                        item.record_key = item.normalized_plate = normalized(record.plate_number)
                        item.plate_number, item.vehicle_id = record.plate_number, record.vehicle_id
                        item.authorized_areas, item.duty_schedule, item.active = record.authorized_areas, record.duty_schedule, record.active
                        # Keep local contact/notes/risk settings while importing registry fields.
                        payload = dict(item.payload or {})
                        for field in ("officer_name", "officer_email", "officer_phone"):
                            setattr(item, field, payload.get(field, ""))
                        payload.update(plate_number=record.plate_number, vehicle_id=record.vehicle_id,
                            department=dept.name, authorized_areas="|".join(record.authorized_areas),
                            duty_schedule=record.duty_schedule, vehicle_type=record.vehicle_type,
                            make=record.make, model=record.model, color=record.color)
                        item.payload = payload
                    elif model is Driver:
                        item.department_id = reference(Department, record.department_external_id).id
                        item.name, item.active = record.name, record.active
                    elif model is VehicleAssignment:
                        item.vehicle_id = reference(Vehicle, record.vehicle_external_id).id
                        item.driver_id = reference(Driver, record.driver_external_id).id
                        item.department_id = reference(Department, record.department_external_id).id
                        item.officer_name = record.officer_name
                    elif model is DutySlip:
                        item.assignment_id = reference(VehicleAssignment, record.assignment_external_id).id
                        for field in ("destination", "purpose", "authorized_areas", "approved_by"):
                            setattr(item, field, getattr(record, field))
                    if model in (VehicleAssignment, DutySlip):
                        item.valid_from, item.valid_until, item.status = record.valid_from, record.valid_until, record.status
                item.vims_source_id, item.vims_external_id, item.vims_payload = source.id, record.external_id, after
                session.flush()
                counts[operation] += 1
                changes.append({"kind": kind, "external_id": record.external_id, "local_id": item.id,
                                "operation": operation, "before": before, "after": after})
        self._vims_validate_relations(session, source.id, batch.exported_at)
        # Keep the current registry display in sync with department renames; capture-time history stays intact.
        for vehicle, dept in session.execute(select(Vehicle, Department).join(Department, Vehicle.department_id == Department.id)
                                             .where(Department.vims_source_id == source.id)):
            if vehicle.payload.get("department") != dept.name:
                vehicle.payload = vehicle.payload | {"department": dept.name}
        return summary, changes

    def _vims_validate_relations(self, session, source_id, as_of):
        # Validate retained records too: partial batches must not invalidate earlier imports.
        assignments = list(session.scalars(select(VehicleAssignment).where(VehicleAssignment.vims_source_id == source_id)))
        active = {}
        for assignment in assignments:
            if assignment.status != "ACTIVE":
                continue
            vehicle = session.get(Vehicle, assignment.vehicle_id)
            driver = session.get(Driver, assignment.driver_id)
            department = session.get(Department, assignment.department_id)
            current = utc(assignment.valid_until) > as_of
            if current and not (vehicle.active and driver.active and department.active):
                raise VimsConflict(f"Assignment {assignment.vims_external_id} references inactive records; cancel it first")
            if current and (vehicle.department_id != department.id or driver.department_id != department.id):
                raise VimsConflict(f"Assignment {assignment.vims_external_id} has inconsistent departments")
            active.setdefault(vehicle.id, []).append(assignment)
        for vehicle_assignments in active.values():
            ordered = sorted(vehicle_assignments, key=lambda a: utc(a.valid_from))
            for previous, current in zip(ordered, ordered[1:]):
                if utc(current.valid_from) < utc(previous.valid_until):
                    raise VimsConflict(f"Overlapping assignments: {previous.vims_external_id}, {current.vims_external_id}")
        for duty in session.scalars(select(DutySlip).where(DutySlip.vims_source_id == source_id)):
            if duty.status != "ACTIVE":
                continue
            assignment = session.get(VehicleAssignment, duty.assignment_id)
            if assignment.status != "ACTIVE":
                raise VimsConflict(f"Duty slip {duty.vims_external_id} references a cancelled assignment")
            if utc(duty.valid_from) < utc(assignment.valid_from) or utc(duty.valid_until) > utc(assignment.valid_until):
                raise VimsConflict(f"Duty slip {duty.vims_external_id} falls outside its assignment period")

    def vims_sources(self):
        with self._lock as session:
            return [{"id": s.id, "name": s.name, "revision": s.revision,
                     "exported_at": utc(s.exported_at).isoformat() if s.exported_at else None}
                    for s in session.scalars(select(VimsSource).order_by(VimsSource.name))]

    def vims_history(self, limit=50, offset=0):
        with self._lock as session:
            query = select(VimsSyncRun, VimsSource).join(VimsSource).order_by(VimsSyncRun.id.desc()).limit(limit).offset(offset)
            return {"total": session.scalar(select(func.count()).select_from(VimsSyncRun)),
                    "items": [run_result(run, source) for run, source in session.execute(query)]}

    def vims_run(self, run_id):
        with self._lock as session:
            run = session.get(VimsSyncRun, run_id)
            if run is None:
                return None
            return run_result(run, session.get(VimsSource, run.source_id)) | {"changes": run.changes}

    def vims_records(self, kind, source=None, limit=100, offset=0):
        model = ENTITIES[kind]
        with self._lock as session:
            query = select(model, VimsSource).join(VimsSource, model.vims_source_id == VimsSource.id)
            if source:
                query = query.where(VimsSource.name == source)
            total = session.scalar(select(func.count()).select_from(query.subquery()))
            items = [{"local_id": item.id, "source": origin.name, **item.vims_payload}
                     for item, origin in session.execute(query.order_by(model.id).limit(limit).offset(offset))]
            return {"total": total, "items": items}
