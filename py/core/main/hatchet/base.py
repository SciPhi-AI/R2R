from hatchet_sdk import Hatchet

try:
    import os

    r2r_hatchet = Hatchet()
except ImportError:
    r2r_hatchet = None
