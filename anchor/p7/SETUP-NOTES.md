# Setup notes - P7 live bridge probe

## Salesforce app type: Connected App, not External Client App

The probe subscribes to `Bridge_Task__e` over the Streaming API (CometD /
Bayeux) using the replay extension. The OAuth 2.0 client-credentials flow
must therefore yield an **opaque session ID**, not a JWT-based access token.

External Client Apps issue JWT-based access tokens and expose no setting to
disable that behaviour - not per app (the app's OAuth Policies offer only
*Named User JWT-Based Access Token Settings*, i.e. timeout) and not org-wide
(*OAuth and OpenID Connect Settings* offers only *Revoke Tokens*). Salesforce
documents JWT-based access tokens as usable "only to access REST APIs".

Observable consequence, and a useful signature if this recurs: platform-event
publish over REST succeeds (HTTP 201) and `/services/data/vXX.X/limits`
returns 200, while every Bayeux handshake is refused with

    error = 403::Handshake denied
    ext.sfdc.failureReason = 401::Authentication invalid

identically across API versions 59.0 / 61.0 / 64.0, both
`Authorization: OAuth <token>` and `Authorization: Bearer <token>`, and both
the My Domain host and the `instance_url` host. The uniformity is the tell:
the transport is rejecting the token *type*, not the header or endpoint.

Use a **Connected App** instead:

- Enable OAuth Settings; selected scope `Manage user data via APIs (api)`
- Enable Client Credentials Flow, and set its Run As user
- Leave *Issue JSON Web Token (JWT)-based access tokens for named users*
  UNCHECKED - this is the control External Client Apps do not expose

Verify from the token response before running the probe: an opaque session ID
begins `00D` and contains `!` in a single segment; a JWT begins `eyJ` and has
two `.` separators. Connected App changes can take up to 10 minutes to take
effect, so a token request made immediately after saving may fail spuriously.

The run-as identity is not fixed by P7-PROBE-DESIGN.md; any active user with
Create on `Bridge_Task__e` and Streaming API access is acceptable.
