# Security policy

## Supported versions

Security fixes are provided for the latest 1.x release.

## Reporting

Do not publish credentials, private screenshots, account UIDs, or exploit details in a public
issue. Use GitHub's private vulnerability reporting feature for this repository when available.

Include:

- affected version and operating system;
- the smallest reproducible input without personal data;
- expected and observed behavior;
- whether the issue involves model files, archive paths, or output overwrite behavior.

## Local-data guarantees

- The application does not upload screenshots, OCR text, rules, or scores.
- OCR models are downloaded only through the explicit `models install` command.
- Model files are recorded and later checked with SHA-256.
- Output replacement requires `--force`.
- Configuration does not require registry, PATH, or Windows environment-variable changes.
- CI audits the installed core, plotting, development, and OCR dependency set for known
  vulnerabilities.

Third-party packages and OCR models retain their own security and update policies.
