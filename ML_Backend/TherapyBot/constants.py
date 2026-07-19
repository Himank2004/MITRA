"""
TherapyBot constants — imports from centralized ML_Backend/constants.py

All model hierarchies, error signals, and debug flags are now centralized
to ensure consistent behavior across all LLM-based components.
"""

# Import centralized constants from parent ML_Backend directory
import sys
import os

# Add parent directory to path to import from ML_Backend/constants.py
_parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

from constants import THERAPY_MODEL_HIERARCHY as MODEL_HIERARCHY
from constants import RATE_LIMIT_SIGNALS, DEBUG_FLAGS

__all__ = ["MODEL_HIERARCHY", "RATE_LIMIT_SIGNALS", "DEBUG_FLAGS"]
