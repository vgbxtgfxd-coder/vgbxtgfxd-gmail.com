"""Pytest configuration."""

import sys
from pathlib import Path

# Add parent dir to path so form_crawler is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
