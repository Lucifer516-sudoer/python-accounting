# database/engine.py
# Copyright (C) 2024 - 2028 the PythonAccounting authors and contributors
# <see AUTHORS file>
#
# This module is part of PythonAccounting and is released under
# the MIT License: https://www.opensource.org/licenses/mit-license.php

"""
Database engine construction for PythonAccounting.

"""

from typing import Any

from sqlalchemy import Engine, create_engine


def get_engine(
    url: str,
    include_deleted: bool = False,
    ignore_isolation: bool = False,
    **kwargs: Any,
) -> Engine:
    """
    Create a database engine with the accounting query filters configured.

    The returned engine carries the execution options that
    :func:`python_accounting.database.session.get_session` reads to configure
    the session's soft-delete and entity-isolation filters.

    Args:
        url (str): The database URL, in sqlalchemy format.
        include_deleted (bool): Include soft-deleted (recycled) records in
            queries. Defaults to False.
        ignore_isolation (bool): Disable entity isolation, exposing records
            from all Entities. Defaults to False.
        **kwargs: Additional keyword arguments passed to
            sqlalchemy's create_engine.

    Returns:
        Engine: The configured database engine.

    """
    return create_engine(url, **kwargs).execution_options(
        include_deleted=include_deleted,
        ignore_isolation=ignore_isolation,
    )
