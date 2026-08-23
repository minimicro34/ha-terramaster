# Security Policy

## Supported versions

The latest released version is supported.

Please update to the most recent release before reporting a security issue.

---

## Reporting a vulnerability

If you believe you have found a security vulnerability in **TerraMaster TOS for Home Assistant**, please **do not** open a public GitHub issue.

Instead, report it privately by contacting the maintainer through GitHub or by email if a contact address is available.

Please include:

- a description of the vulnerability;
- affected version(s);
- steps to reproduce;
- potential impact;
- any suggested mitigation.

---

## Sensitive information

Never publish or include the following in bug reports, issues, pull requests, or discussions:

- TerraMaster NAS credentials
- SSH usernames or passwords
- SSH private keys
- Home Assistant secrets
- authentication tokens or session information
- public or private IP addresses when sensitive
- Home Assistant diagnostics containing authentication or security-sensitive data
- command output containing credentials or private system information
- any other private authentication or security information

Please remove or redact sensitive information before sharing logs, diagnostics, screenshots, or command output.

---

## Scope

This integration communicates directly with TerraMaster TOS devices over SSH.

Security reports related to:

- SSH authentication;
- credential and key storage;
- command execution;
- privilege handling;
- input validation;
- sensitive NAS information exposure;
- Home Assistant service interactions;

are especially appreciated.

---

Thank you for helping keep TerraMaster TOS for Home Assistant secure.