---
description: Security Hardening Plan for BE_MamaStoria_v3
---

# Security Hardening Steps

## 1. Secure Healtheck Implementation
- **File**: `app/main.py`
- [ ] Remove `health/db` endpoint details (env vars, socket paths).
- [ ] Keep only basic connectivity status.

## 2. Secure User Endpoints
- **File**: `app/api/users.py`
- [ ] Remove `debug_kredit` endpoint.
- [ ] Add Admin Role check to `update_kredit`.
- [ ] Ensure `update_kredit` is not accessible by regular users.

## 3. Standardize & Secure Comic Generator Routes
- **File**: `app/main.py`
- [ ] Move `comic_generator.router` to prefix `/api/v1`.
- [ ] Ensure paths are consistent (e.g., `/api/v1/generate/script` instead of `/api/script`).
- **File**: `app/api/comic_generator.py`
- [ ] `render_part`: Add authentication/admin check or disable in production.
- [ ] `health-check-ai`: Restrict or sanitize output.

## 4. Rate Limiting (Future)
- [ ] Add `slowapi` to requirements.txt (Pending User Approval).
