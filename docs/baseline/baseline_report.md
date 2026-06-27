# Baseline Report — Processual Maestro Kernel v1.9.0

## Test Results (Pre-Migration)
- 78 tests passing
- All existing test suites green

## Current Architecture
- cgtlib/ — CGT formal core (39 modules)
- processual_kernel/ — Maestro kernel with adaptive governance
- tests/ — 18 test files
- examples/ — 3 examples
- ui/ — HTML dashboard

## Key Modules Containing Raw Equations
- cgtlib/fate.py — FateVector computation, rank classification
- cgtlib/existence.py — Existential score computation
- cgtlib/possibility.py — Constrained possibility computation
- cgtlib/lift.py — Dynamic lift computation
- cgtlib/gates.py — Transmissibility, delay gate, transition channel
- cgtlib/evaluators.py — Structural transition evaluation
- cgtlib/aftermath.py — Collapse and flourishing indicators

## Security Layer
- processual_kernel/adaptive/encryption.py — AES-256-GCM support

## Date
Baseline captured: May 2026
