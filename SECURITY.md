# Security Policy

## Design note

LinguaPal is built to keep a learner's data local. By default the app stores everything
in a single SQLite file on the same machine, and talks only to an OpenAI-compatible
model endpoint that you configure. Nothing is sent anywhere else.

When you host the app, treat the deployment like any small web service:

- set `LLM_API_KEY` (and any other secrets) as environment variables, never in the repo;
- put the app behind HTTPS;
- restrict who can reach the public URL, since anyone who can reach it can use the
  configured model endpoint.

## Reporting a vulnerability

Please do not open a public issue for security problems. Instead, report it privately
via GitHub's **Security → Report a vulnerability** tab on the repository. Include:

- a description of the issue and its impact,
- steps to reproduce,
- the version or commit you tested.

You can expect an initial acknowledgement within a few days.
