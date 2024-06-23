from typing import Optional

from .assembly.builder import R2RAppBuilder

# Global variable to store the R2RApp instance
r2r_app_instance = None


def get_r2r_app(app_builder: Optional[str] = None):  # , *args, **kwargs):
    global r2r_app_instance
    if r2r_app_instance is None:
        builder = app_builder or R2RAppBuilder()
        r2r_app_instance = builder.build()  # *args, **kwargs)
    return r2r_app_instance
