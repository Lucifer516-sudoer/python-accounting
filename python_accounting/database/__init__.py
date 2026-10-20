# python_accounting/database/__init__.py
# Copyright (C) 2024 - 2028 the PythonAccounting authors and contributors
# <see AUTHORS file>
#
# This module is part of PythonAccounting and is released under
# the MIT License: https://www.opensource.org/licenses/mit-license.php

"""
Database engine and session construction for PythonAccounting.

"""

from python_accounting.database.engine import get_engine
from python_accounting.database.session import get_session

__all__ = ["get_engine", "get_session"]
