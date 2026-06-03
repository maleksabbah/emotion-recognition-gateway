# EmotionRecognitionGateway

Public API gateway for the Mntis facial emotion recognition platform.
It is the only publicly exposed HTTP service: it authenticates requests
(JWT), validates input, and proxies to the internal orchestrator and
storage services. It owns the `gateway_db` (users / auth).

Built with FastAPI. Interactive API docs at `/docs`.

## Architecture

The service follows a clean, layered architecture where each layer has
one responsibility and depends only on the layer beneath it:

* **Routes** — thin HTTP controllers. Auth, upload (presign + complete),
  sessions (status + download), and user routes. They translate between
  HTTP requests/responses and DTOs and call the service layer. No
  business logic lives here.
* **Services** — the business logic. `AuthService` (register, login,
  token issuance, password hashing), `JobService` (orchestrates upload
  + session creation by talking to the downstream services), and
  `FileProxyService` (resolves session-scoped download URLs through
  the storage service). Knows nothing about HTTP.
* **Repositories** — data access. Wraps the user database, the Redis
  refresh-token store, and the typed HTTP clients for the downstream
  services (`OrchestratorClient`, `StorageClient`) so the service
  layer never touches raw queries, redis, or HTTP clients directly.
* **Entities** — the User ORM model and any auxiliary domain types.
* **Dtos** — request/response shapes (`RegisterRequest`,
  `LoginResponse`, `PresignRequest`, `SessionStatusResponse`, ...)
  kept separate from internal entities.
* **Config** — wiring: SQLAlchemy session, Redis client, httpx client,
  JWT secret + algorithm + lifetimes, downstream service URLs.

This separation keeps the HTTP layer swappable, the business logic
testable in isolation, and the data layer free to change without
touching the rest.

Here the repository layer also includes thin HTTP clients for the
downstream services (orchestrator, storage), so the service layer
proxies through a clean interface rather than calling them directly.

Part of a multi-service system — see the [platform overview](../EmotionRecognitionDocker)
for the full architecture, pipeline flow, and the other services.
