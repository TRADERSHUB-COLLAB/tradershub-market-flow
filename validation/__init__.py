"""Private 30-trading-day Market Pulse validation harness.

The harness runs the Market Flow scoring engine each trading day, persists the
resulting pulse into a local SQLite database, and produces reports and replays
so that scoring drift, regime instability, or silent behaviour changes can be
detected before touching the live homepage.
"""
