# Documentation Home

Welcome to the documentation for the Energy Sector Cybersecurity RAG Assistant.

This documentation is written for two groups:

- First-time users who want to install and use the app.
- Future maintainers who need to understand how it works.

If you are new to terminals, Python, or environment variables, start with the beginner path below.

## Beginner Path

1. Read [Getting Started](getting-started.md).
2. Follow [Installation](installation.md).
3. Create your settings with [Configuration](configuration.md).
4. Complete [First Run](first-run.md).
5. Learn the app with [Daily Usage](daily-usage.md).
6. Keep [Troubleshooting](troubleshooting.md) nearby.

## Maintainer Path

1. Read [Architecture](architecture.md).
2. Review [Project Structure](project-structure.md).
3. Read [Developer Guide](developer-guide.md).
4. Review [Maintenance](maintenance.md).
5. Review [Security](security.md).

## Reference

- [Features](features.md)
- [Administration](administration.md)
- [Deployment](deployment.md)
- [Data and Storage](database.md)
- [API](api.md)
- [Authentication](authentication.md)
- [Backup and Restore](backup-and-restore.md)
- [Upgrading](upgrading.md)
- [FAQ](faq.md)
- [Glossary](glossary.md)
- [Contributing](contributing.md)
- [Appendix](appendix.md)

## What This Project Does

This application answers energy-sector cybersecurity questions by searching a document collection and asking an AI model to write a grounded answer.

The short version:

1. You ask a question.
2. The app searches trusted document chunks.
3. The app sends the most relevant chunks to OpenAI.
4. OpenAI writes an answer using that evidence.
5. The app shows the answer and sources.

## What This Project Does Not Include

The repository does not include:

- User login or account management.
- A public HTTP API.
- A traditional relational database.
- Docker or container setup.
- A documented production deployment pipeline.
