# TechConf — Product Overview

## Business Domain

TechConf is a microservices platform for managing the full lifecycle of technical conferences (cloud, AI, security). It enables a company to handle users, events, registrations, feedback, and notifications through a set of independently deployable HTTP services.

## Core Business Entities

| Entity | Service | Description |
|---|---|---|
| User | user-service | Participants, speakers, and organizers of conferences |
| Event | event-service | Conferences with lifecycle (draft → published → cancelled) and venue capacity |
| Registration | registration-service | A user's confirmed seat at a published event |
| Feedback | feedback-service | Post-event ratings (1–5) submitted by registered attendees |
| Notification | notification-service | Messages (email, sms, push) sent individually or broadcast to event attendees |

## Service Dependency Map

```
user-service  ◄────────────────────────────────┐
     ▲                                          │
     │         event-service ◄─────────────────┤
     │               ▲                          │
     └───────────────┤                          │
          registration-service ◄────────────────┤
                     ▲            ▲             │
                     │            │             │
             feedback-service  notification-service
```

Dependency order (safe to build in this sequence):
1. **user-service** — no upstream dependencies
2. **event-service** — calls user-service (validate organizer)
3. **registration-service** — calls user-service + event-service
4. **feedback-service** *(optional)* — calls registration-service + event-service
5. **notification-service** *(optional)* — calls user-service + registration-service

## Service Ports

| Service | Dev Port | Acceptance Port |
|---|---|---|
| user-service | 5001 | 15001 |
| event-service | 5002 | 15002 |
| registration-service | 5003 | 15003 |
| feedback-service | 5004 | 15004 |
| notification-service | 5005 | 15005 |

## Mandatory vs Optional

- **Mandatory (3):** user-service, event-service, registration-service
- **Optional/Bonus (2):** feedback-service, notification-service

## Exam Constraints

- All services must be declared in `services.yaml` (root) to be tested by the acceptance suite.
- Services NOT declared in `services.yaml` are **skipped**, not failed.
- Protected files (never modify): `contracts/openapi/*.yaml`, `contracts/validator.py`, `tests/integration/`, `CHECKSUMS.sha256`.
- Penalty for modifying protected files: **−20 points**.
