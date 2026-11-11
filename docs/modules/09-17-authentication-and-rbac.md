# Module 9.17: Authentication and department access

Updated 10 October 2026. The first implementation phase adds department access,
account administration, session revocation and the reporting/audit foundation in
[module 9.16](09-16-reporting-and-audit.md).

## Current behavior

Users are stored in PostgreSQL with bcrypt password hashes. Administrators create
accounts, reset passwords, change roles, assign one department per officer, disable
accounts and revoke sessions from **User access**. Account emails are fixed to
preserve audit identity. An administrator cannot disable or demote their own account.

JWT access tokens expire after eight hours. Every authenticated request checks the
current active account, role and token version in the database. Changing an account
or revoking sessions invalidates its earlier tokens immediately. Signing out revokes
all sessions for that account. Department permissions are not trusted from token claims.

Existing Transport/Supervisory accounts start unassigned after migration and see no
department records until an administrator assigns a department. No departments are
guessed from email addresses, names or existing fleet records.

## Roles

| Capability | Administrator | Transport Officer | Supervisory Officer | Auditor |
|---|---|---|---|---|
| Operational records | All | Assigned department | Assigned department | No |
| Accounts, registry, VIMS, zones and integration settings | Manage | No | No | No |
| Evidence/ANPR review | All | Department | Department | No |
| Duty destination/purpose review | All | No | Department | No |
| Challan drafting and appeal recording | All | Department | Department | No |
| Approve/reject and decide appeals | Independent review | No | Department, independent review | No |
| Issue an approved case | Yes | Department | Department | No |
| Amend draft fine | Yes | Department | No | No |
| Notification dispatch | Yes | No | Department | No |
| Report generation/export | All | Department | Department | All |
| Audit history | All | No | Department | All |
| Raw camera, frame events, live feed and full images | Yes | No | No | No |
| Plate crop download | All | Department | Department | No |

Risk tasks additionally enforce their assigned officer role. Case approval and appeal
resolution retain the existing independent-officer requirements.

## Ownership

`backend/access.py` holds a request-local principal. SQLAlchemy query criteria apply
before pagination, counts, joins and dashboard aggregation, including direct record
lookups. The API uses these criteria for the registry, sightings, detections,
recognitions, evidence, duties, risk tasks, digital twins and challans.

Sightings and evidence store department IDs from the capture snapshot. A registry
transfer does not transfer access to old observations. Correcting an uncertain
plate through administrator review assigns its evidence to the corrected department.
Historical VIMS context is filtered before entering scoped profile/duty responses.
Unknown/unattributed records remain available to administrators.

Challans containing multiple departments, or involving a vehicle subsequently
transferred away from the case department, require administrator handling. This
prevents a frozen case or current officer details from exposing another department.
Migration uses captured department names to backfill IDs, without guessing from the
vehicle's current department. Unresolvable legacy ownership remains unassigned.

Full frames may contain other vehicles even when only one plate was recognized.
Scoped image URLs and ZIP packages expose only owned plate crops. Newly issued PDFs
embed only plate crops; historical PDFs without that image policy require
administrator access. Original issued documents are never overwritten.

## APIs and source

| Route | Purpose |
|---|---|
| `POST /api/auth/login` | Authenticate and issue access token |
| `GET /api/auth/me` | Current account and department |
| `POST /api/auth/logout` | Revoke the account's sessions |
| `GET/POST /api/users` | Administrator account list/create |
| `PUT /api/users/{id}` | Edit role, department, active state or password |
| `POST /api/users/{id}/revoke` | Invalidate existing tokens |
| `GET /api/departments` | Accessible active departments |
| `POST /api/camera/session-token` | Administrator upload token, 20 minutes |
| `POST /api/live-camera/session-token` | Administrator feed token, 20 minutes |

Authentication/middleware: `backend/auth.py`, `backend/main.py`.
Scope queries: `backend/access.py`. Account API: `backend/governance_api.py`.
Schema: migration `0005_department_access`. UI: `GovernancePages.tsx`, `Navbar.tsx`
and `AuthContext.tsx`. WebSockets revalidate sessions before broadcasts and while idle.
Image/download query tokens have the same current-account checks as API calls.

## Demonstration

1. Sign in as the existing administrator (`admin@justmeter.gov`; original demo
   password `admin123`, unless already changed).
2. Open **User access** and assign the Transport and Supervisory accounts to an
   existing department. Demo passwords remain unchanged unless reset.
3. Sign in as Transport Officer and inspect Fleet, Spotted, Evidence and Cases.
   Only owned records appear. Another department's direct URL returns 404.
4. Generate a report and verify its totals use the same department restriction.
5. Sign in as Auditor: Reports and Audit are available; operational tabs are absent.
6. Revoke an officer's sessions from the administrator screen. Their next request
   returns 401 and the dashboard returns to login.

## Remaining limitations

Each officer has one department; delegated memberships and a cross-department case
reassignment process are future work. Camera department binding/redaction is also
future work, so raw camera operation is administrator-only. MFA, self-service password
recovery and a device-by-device session list are absent.

This is application-level query isolation, not PostgreSQL row-level security.
Future endpoints must use the ORM/session access layer; arbitrary Core SQL does not
inherit these rules. Sessions must never be shared between requests or principals.
Demo credentials and localStorage-based token storage remain prototype choices.
