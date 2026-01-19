"""Pytest configuration for CUMTD Bus tests."""

import sys
from pathlib import Path

# Add custom_components to path so we can import properly
sys.path.insert(0, str(Path(__file__).parent.parent))
