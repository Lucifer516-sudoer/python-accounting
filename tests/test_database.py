# tests/test_database.py
# Copyright (C) 2024 - 2028 the PythonAccounting authors and contributors
# <see AUTHORS file>
#
# This module is part of PythonAccounting and is released under
# the MIT License: https://www.opensource.org/licenses/mit-license.php

"""
Tests for the database package's public engine/session constructors.

"""

from sqlalchemy import Engine

from python_accounting.database import get_engine, get_session
from python_accounting.database.session import AccountingSession


class TestDatabase:
    """Tests for get_engine and get_session."""

    def test_get_engine_returns_configured_engine(self) -> None:
        engine = get_engine("sqlite://")

        assert isinstance(engine, Engine)
        options = engine.get_execution_options()
        assert options["include_deleted"] is False
        assert options["ignore_isolation"] is False

    def test_get_engine_execution_options(self) -> None:
        engine = get_engine("sqlite://", include_deleted=True, ignore_isolation=True)

        options = engine.get_execution_options()
        assert options["include_deleted"] is True
        assert options["ignore_isolation"] is True

    def test_get_engine_passes_create_engine_kwargs(self) -> None:
        engine = get_engine("sqlite://", echo=True)

        assert engine.echo is True

    def test_get_session_returns_accounting_session(self) -> None:
        engine = get_engine("sqlite://")

        session = get_session(engine)

        assert isinstance(session, AccountingSession)
        assert session.info["include_deleted"] is False
        assert session.info["ignore_isolation"] is False
        session.close()
