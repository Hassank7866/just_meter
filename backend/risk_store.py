"""Risk persistence and an internal officer review queue; no external dispatch."""
from copy import deepcopy
from datetime import timedelta

from sqlalchemy import select

from .config import get_local_now
from .db_models import AuditEvent, RiskAssessment, RiskPolicy, RiskTask, Sighting, Vehicle
from .risk_engine import RiskPolicyConfig, score_risk


class RiskStore:
    def _policy(self, session):
        policy = session.scalar(select(RiskPolicy).order_by(RiskPolicy.version.desc()).limit(1))
        if policy is None:
            policy = RiskPolicy(version=1, created_at=get_local_now(), created_by="system",
                                config=RiskPolicyConfig().model_dump())
            session.add(policy)
            session.flush()
        return policy

    def get_risk_policy(self):
        with self._lock as session:
            policy = self._policy(session)
            return {"version": policy.version, "config": deepcopy(policy.config),
                    "created_at": policy.created_at.isoformat(), "created_by": policy.created_by}

    def update_risk_policy(self, config, actor, expected_version):
        config = RiskPolicyConfig.model_validate(config).model_dump()
        with self._lock as session:
            old = self._policy(session)
            if expected_version != old.version:
                raise ValueError("Policy changed; reload before saving")
            policy = RiskPolicy(version=old.version + 1, config=config,
                                created_at=get_local_now(), created_by=actor)
            session.add(policy)
            session.add(AuditEvent(occurred_at=get_local_now(), actor=actor,
                action="RISK_POLICY_CREATED", entity=str(policy.version), details={"previous_version": old.version, "config": config}))
            session.flush()
            return {"version": policy.version, "config": deepcopy(config)}

    def _score_current_risk(self, session, compliance, plate, detected_at, vehicle):
        policy = self._policy(session)
        start = detected_at - timedelta(days=policy.config["recurrence_days"])
        vehicle_id = session.scalar(select(Vehicle.id).where(Vehicle.normalized_plate == plate))
        identity = Sighting.vehicle_id == vehicle_id if vehicle_id else Sighting.normalized_plate == plate
        history = list(session.scalars(select(Sighting).where(
            identity, Sighting.status == "VIOLATION",
            Sighting.observed_at >= start, Sighting.observed_at < detected_at)))
        severe = sum(r.payload.get("risk_level") in {"HIGH", "CRITICAL"} for r in history)
        result = score_risk(compliance, policy.config, prior_count=len(history), prior_severe_count=severe,
                            assignment_context=(vehicle or {}).get("risk_context", ""), policy_version=policy.version)
        return policy, result

    def _persist_risk(self, session, sighting, policy, result):
        assessment = RiskAssessment(sighting_id=sighting.id, policy_id=policy.id,
            assessed_at=get_local_now(), score=result["risk_score"], level=result["risk_level"], result=result)
        session.add(assessment)
        session.flush()
        if result["recommended_action"] != "NONE":
            session.add(RiskTask(assessment_id=assessment.id, priority=result["notification_priority"],
                assigned_role=result["escalation_role"], recommended_action=result["recommended_action"], status="OPEN"))
        session.add(AuditEvent(occurred_at=get_local_now(), actor="system", action="RISK_ASSESSED",
                              entity=str(assessment.id), department_id=sighting.department_id,
                              details={"sighting_id": sighting.id, "policy_version": policy.version}))

    def get_risk_tasks(self, status="OPEN", limit=200):
        with self._lock as session:
            query = select(RiskTask, RiskAssessment, Sighting).join(
                RiskAssessment, RiskTask.assessment_id == RiskAssessment.id).join(
                Sighting, RiskAssessment.sighting_id == Sighting.id)
            if status:
                query = query.where(RiskTask.status == status)
            query = query.order_by(RiskAssessment.score.desc(), RiskTask.id.desc()).limit(limit)
            return [{"id": task.id, "status": task.status, "assigned_role": task.assigned_role,
                     "priority": task.priority, "recommended_action": task.recommended_action,
                     "acknowledged_by": task.acknowledged_by,
                     "plate_number": sighting.payload.get("plate_number", ""),
                     "department": sighting.payload.get("department", ""),
                     "timestamp": sighting.payload.get("timestamp", ""),
                     "violation_id": sighting.violation_id, **assessment.result}
                    for task, assessment, sighting in session.execute(query)]

    def acknowledge_risk_task(self, task_id, actor, role):
        with self._lock as session:
            task = session.get(RiskTask, task_id)
            if task is None:
                return None
            if role not in {"Administrator", task.assigned_role}:
                raise PermissionError("This task belongs to another officer role")
            if task.status != "ACKNOWLEDGED":
                task.status = "ACKNOWLEDGED"
                task.acknowledged_by = actor
                task.acknowledged_at = get_local_now()
                session.add(AuditEvent(occurred_at=get_local_now(), actor=actor, action="RISK_TASK_ACKNOWLEDGED",
                    entity=str(task.id), department_id=session.get(Sighting, session.get(RiskAssessment, task.assessment_id).sighting_id).department_id,
                    details={"assessment_id": task.assessment_id}))
            return {"id": task.id, "status": task.status, "acknowledged_by": task.acknowledged_by}
