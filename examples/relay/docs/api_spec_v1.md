# Relay API specification (v1)

## 1. rate_limit

Requests are budgeted per access_token: 600 requests per rolling minute.
Responses carry X-RateLimit-Remaining. Exceeding the budget returns 429
with a Retry-After header.

## 2. idempotency_key

A client-supplied unique key on mutating requests. Replays with the same
key return the original result and are never re-executed.

## 3. pagination_cursor

An opaque token in list responses. Pass it back as ?cursor= to fetch the
next page. Cursors are stable across inserts.

## 4. webhook

A webhook is a signed POST Relay sends to a subscriber URL on an event.
Delivery is at-least-once; consumers deduplicate via idempotency_key.
Webhook subscriptions are managed under an authenticated session.

## 5. session (superseded)

Earlier drafts of this spec defined "session" as the TCP keep-alive window.
That definition collided with the auth design's session and was superseded;
see the registry collision record. The auth definition is canonical.
