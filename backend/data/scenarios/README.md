Phase 3/5 scenario contracts:
- insider-data-theft: simulated employee reads a synthetic finance decoy then touches backup breadcrumb.
- credential-lateral-movement: synthetic credential-note touch followed by simulated auth and jump-host progression.
- slow-scan-theft: low-rate synthetic discovery followed by staged decoy reads.
- benign-backup-noise: allow-listed synthetic backup actor; evaluation must measure false positives rather than silently suppressing events.
All steps must be recorded as simulator events with deterministic run IDs and reset support.
