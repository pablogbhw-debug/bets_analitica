"""Fachada retrocompatible; la implementación MVC vive en models.database."""

import sys
from models import database as _modelo_database

sys.modules[__name__] = _modelo_database
