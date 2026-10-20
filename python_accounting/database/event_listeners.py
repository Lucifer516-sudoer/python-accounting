# database/event_listeners.py
# Copyright (C) 2024 - 2028 the PythonAccounting authors and contributors
# <see AUTHORS file>
#
# This module is part of PythonAccounting and is released under
# the MIT License: https://www.opensource.org/licenses/mit-license.php

"""
This mixin provides logic for handling events in sqlalchemy's orm lifecycle
that are relevant to accounting.

"""

from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

from sqlalchemy import event, orm, and_, update
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Mapper, Session

from python_accounting.database.accounting_functions import AccountingFunctionsMixin
from python_accounting.models import Entity, Recyclable, Transaction, Account, Ledger
from python_accounting.mixins import IsolatingMixin
from python_accounting.exceptions import MissingEntityError

if TYPE_CHECKING:
    from sqlalchemy import Select

    from python_accounting.database.session import AccountingSession


def _filter_options(execute_state: "orm.ORMExecuteState", option: str) -> bool:
    return (
        not execute_state.is_column_load
        and not execute_state.is_relationship_load
        and not execute_state.execution_options.get(option, False)
        and not execute_state.session.info.get(option, False)
    )


class EventListenersMixin(AccountingFunctionsMixin):
    """
    Event Listeners class.
    """

    # The listeners below are registered on the Session/Ledger classes and are
    # invoked with the documented event arguments, not with the mixin instance
    # as self. They are declared static so their first parameters are typed as
    # what they actually receive; registration order (event.listens_for below
    # staticmethod) is unchanged, so the registry still holds the raw function.

    @staticmethod
    @event.listens_for(Session, "do_orm_execute")
    def _add_filtering_criteria(
        execute_state: "orm.ORMExecuteState",
    ) -> None:
        # Recycling filter
        if _filter_options(execute_state, "include_deleted"):
            execute_state.statement = execute_state.statement.options(
                orm.with_loader_criteria(
                    Recyclable,
                    lambda cls: and_(
                        cls.deleted_at == None,  # noqa: E711
                        cls.destroyed_at == None,  # noqa: E711
                    ),
                    include_aliases=True,
                )
            )

        # Entity filter
        if (
            _filter_options(execute_state, "ignore_isolation")
            and cast("Select[Any]", execute_state.statement).column_descriptions[0][
                "type"
            ]
            is not Entity
        ):
            session_entity_id = cast(
                "AccountingSession", execute_state.session
            ).entity.id
            execute_state.statement = execute_state.statement.options(
                orm.with_loader_criteria(
                    IsolatingMixin,
                    lambda cls: cls.entity_id == session_entity_id,
                    include_aliases=True,
                )
            )

    @staticmethod
    @event.listens_for(Session, "transient_to_pending")
    def _set_session_entity(session: "AccountingSession", object_: Any) -> None:
        if not hasattr(session, "entity") or session.entity is None:
            if isinstance(object_, Entity):
                session.entity = object_
            elif object_.entity_id is None:
                raise MissingEntityError
            else:
                entity = session.get(Entity, object_.entity_id)
                if entity is None:
                    # The referenced Entity row does not exist (e.g. it was
                    # recycled); the session cannot be scoped without it.
                    raise MissingEntityError
                session.entity = entity

        if (
            session.entity.reporting_period is None
            or session.entity.reporting_period.calendar_year != datetime.today().year
        ):
            session._set_reporting_period()

    @staticmethod
    @event.listens_for(Session, "transient_to_pending")
    def _set_object_index(session: "AccountingSession", object_: Any) -> None:
        if (isinstance(object_, (Account, Transaction))) and object_.id is None:
            object_.session_index = (
                len(
                    [
                        t
                        for t in session.new
                        if isinstance(t, Transaction)
                        and t.transaction_type == object_.transaction_type
                    ]
                )
                if isinstance(object_, Transaction)
                else len(
                    [
                        a
                        for a in session.new
                        if isinstance(a, Account)
                        and a.account_type == object_.account_type
                    ]
                )
            )

    @staticmethod
    @event.listens_for(Ledger, "after_insert")
    def _set_ledger_hash(
        mapper: "Mapper[Ledger]", connection: Connection, target: Ledger
    ) -> None:
        connection.execute(
            update(Ledger)
            .where(Ledger.id == target.id)
            .values(hash=target.get_hash(connection))
        )

    @staticmethod
    @event.listens_for(Session, "before_flush")
    def _validate_model(session: "AccountingSession", _: Any, __: Any) -> None:
        for model in list(session.new) + list(session.dirty):
            validate = getattr(model, "validate", None)
            if validate is not None:
                validate(session)
