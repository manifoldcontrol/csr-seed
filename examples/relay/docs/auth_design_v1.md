# Relay auth design (v1)

## 1. session

A session is a server-side record binding one client to one scope set for a
bounded lifetime. Sessions are created on token exchange and revoked on
logout or expiry. All authenticated endpoints resolve a session first;
nothing else confers authenticated identity.

## 2. access_token

The access_token is the bearer credential a client presents to open a
session. Formerly named "api_key" (renamed in v1: keys are static, tokens
rotate). Opaque string, 32 bytes, rotates on a 24h schedule.

## 3. scope

A scope is a named capability grant attached to a session. Endpoints declare
required scopes; the gateway enforces them before dispatch.
