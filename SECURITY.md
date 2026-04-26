# Arachne — Security Policy

## Supported Versions

| Version | Supported |
| ------- | --------- |
| 0.x.x   | ✅ |

## Reporting a Vulnerability

We take security seriously. If you discover a security issue:

1. **Do NOT** report through public GitHub issues
2. Contact the maintainer directly at **dan@strategicautomation.com** with:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested mitigations (if any)

## Security Features
- Environment-based configuration (no hardcoded secrets)
- `SecretStr` for all API keys and sensitive values
- `.env` files in `.gitignore`
- Deno sandbox for custom TypeScript tools
- Pointer pattern prevents massive output in context windows

## Known Security Issues (Being Addressed)
1. **Custom Python tools** loaded via `exec_module` without sandboxing. Fix in progress.
2. **Path traversal** in `read_file`/`write_file` — realpath check insufficient. Fix planned.
3. **Session Data Exposure:** Mission-critical data in session logs not yet encrypted.

## Best Practices
- Never commit `.env` or secrets
- Run agents with minimal filesystem permissions
- Review auto-generated tool code before deployment
- Use Deno sandbox over Python sandbox when possible
