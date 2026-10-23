# PesaGuard Internal Registry System

A secure internal registry ingestion and lookup service for PesaGuard. The service ingests authorized corporate registry datasets, preserves source provenance, normalizes records, and exposes authenticated lookup APIs. A local record is not, by itself, proof of authoritative KYB verification.

## Status
Implementation is in progress. Configure credentials using environment variables; never commit `.env` or production secrets.
