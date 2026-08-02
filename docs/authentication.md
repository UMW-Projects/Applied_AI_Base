# Authentication

Authentication means proving who a user or service is.

## User Login

No user login system was found.

The Streamlit app does not define:

- User accounts.
- Passwords.
- Roles.
- Permissions.
- Session database.

## Service Authentication

The project authenticates to external services with API keys.

| Service | Key |
| --- | --- |
| OpenAI | `OPENAI_API_KEY` |
| Pinecone | `PINECONE_API_KEY` |
| SerpAPI | `SERPAPI_API_KEY` or `SERPAPI_KEY` |

Store these in `.env` for local use.

## Deployment Warning

Because there is no built-in user login, do not expose the app publicly without adding access control outside the application.

Common options are:

- Private network access.
- VPN.
- Reverse proxy with login.
- Cloud platform authentication.

TODO: Information could not be determined automatically: the intended production authentication method.
