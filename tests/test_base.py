# tests/test_base.py
# Copyright (C) 2024 - 2028 the PythonAccounting authors and contributors
# <see AUTHORS file>
#
# This module is part of PythonAccounting and is released under
# the MIT License: https://www.opensource.org/licenses/mit-license.php

from datetime import datetime

from python_accounting.models import Account, Currency


def test_timestamp_column_defaults_are_callable():
    """The created_at/updated_at defaults must be evaluated per insert."""

    # Account uses joined-table inheritance, so the timestamp columns declared
    # on Base live on the parent recyclable table and are reached via the
    # mapper rather than Account.__table__.c.
    columns = Account.__mapper__.columns

    created_default = columns["created_at"].default
    updated_default = columns["updated_at"].default
    assert created_default is not None
    assert updated_default is not None
    assert created_default.is_callable
    assert updated_default.is_callable


def test_timestamps_reflect_insert_time(session, entity):
    """A freshly inserted record is stamped with the current time."""

    before = datetime.now()

    record = Currency(name="Test Euro", code="EUR", entity_id=entity.id)
    session.add(record)
    session.commit()
    record = session.get(Currency, record.id)

    assert record.created_at >= before
    assert record.updated_at >= before
