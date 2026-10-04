# Swagger UI distribution assets

Unmodified assets from official Swagger UI **v5.33.1**, released October 1, 2026.
Verified as the latest stable official release on October 4, 2026.

- Repository: https://github.com/swagger-api/swagger-ui
- Immutable commit: `cac3d136b5e37bfbe3288c8591f6f4fcf9870599`
- Files: `dist/swagger-ui-bundle.js`, `dist/swagger-ui.css`, root `LICENSE`
- License: Apache-2.0; the upstream license is included here.
- `manifest.json` records SHA-256 and upstream Git blob identifiers.

These assets are self-hosted to preserve the same-origin script policy and avoid
runtime CDN access. The initializer is external, remote validation is disabled,
and authorization is not persisted. This does not authenticate public metadata;
API operations retain the server's existing authentication policy.

For an upgrade, verify official release metadata, download from the immutable
commit, verify Git blob identifiers, update this record and the manifest, then
run the documentation regressions, full suite, and wheel verification. Check the
upstream release/security notes and review the JS supply chain as well as Python
dependencies. Asset hashes are integrity/provenance evidence, not a security audit.
