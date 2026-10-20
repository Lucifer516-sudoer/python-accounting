# database/session_overrides.py
# Copyright (C) 2024 - 2028 the PythonAccounting authors and contributors
# <see AUTHORS file>
#
# This module is part of PythonAccounting and is released under
# the MIT License: https://www.opensource.org/licenses/mit-license.php

"""
This mixin overrides some of sqlalchemy session's in built methods to provide
accounting specific behavior. It also provides custom methods specific to accounting.

"""

from datetime import datetime
from typing import Any, TypeVar, cast

from sqlalchemy import select
from sqlalchemy.orm import Mapper, Session

from python_accounting.models import Recyclable, Recycled, Entity, Assignment
from python_accounting.exceptions import SessionEntityError

# The model type fetched by SessionOverridesMixin.get. Unbound to mirror the
# base Session.get TypeVar exactly (a bound TypeVar is an incompatible
# generic override); the primary-key surface is recovered at the single use
# site below.
_O = TypeVar("_O")


class SessionOverridesMixin(Session):
    """
    Session overrides class.

    Attributes:
        entity (Entity): The Entity currently associated with the session. Set by
            EventListenersMixin's transient_to_pending listener; read here to scope
            deletes to the session's Entity.
    """

    entity: "Entity"

    def get(
        self, entity: "type[_O] | Mapper[_O]", ident: Any, **kwargs: Any
    ) -> "_O | None":
        """
        Overrides sqlalchemy the get method to use select thereby ensuring global filters
        are applied.

        Args:
            entity (`DeclarativeBase`): The model class.
            ident (`int`): The primary key of the instance being fetched.

        Returns:
            The model instance if found, else None.

        """
        if isinstance(entity, Mapper):
            entity = entity.class_

        # Every accounting model carries the Recyclable primary-key surface;
        # the caller's entity argument determines the actual type.
        model = cast("type[Recyclable]", entity)
        return cast(
            "_O | None",
            self.scalar(
                select(model).where(model.id == ident).execution_options(**kwargs)
            ),
        )

    def delete(self, instance: object) -> None:
        """Overrides the sqlalchemy delete method to enable model recycling.

        Args:
            instance (`DeclarativeBase`): The model instance.

        Returns:
            None

        Raises:
            SessionEntityError: If the instance being deleted is the session Entity.
        """

        if isinstance(instance, Assignment):
            self.erase(instance)
            return

        validate_delete = getattr(instance, "validate_delete", None)
        if validate_delete is not None:
            validate_delete(self)

        if isinstance(instance, Entity) and instance.id == self.entity.id:
            raise SessionEntityError

        # Every non-Assignment instance routed here is a soft-deletable model,
        # i.e. a Recyclable subclass.
        recyclable = cast("Recyclable", instance)
        recyclable.deleted_at = recyclable.updated_at = datetime.now()

        self.add(
            Recycled(
                recycled_id=recyclable.id,
                entity_id=self.entity.id,
            )
        )
        self.commit()

    def restore(self, instance: Recyclable) -> bool:
        """Restore a deleted/recycled model instance.

        Args:
            instance (`DeclarativeBase`): The model instance.

        Returns:
            True if successful, else False.

        """

        if instance.destroyed_at is not None:
            return False  # destroyed models cannot be restored

        recycled = instance.history[-1]
        instance.deleted_at = None
        instance.updated_at = recycled.restored_at = datetime.now()
        self.commit()
        return True

    def destroy(self, instance: Recyclable) -> None:
        """Mark a model instance as destroyed, i.e. permanently delete.

        Args:
            instance (`DeclarativeBase`): The model instance.

        Returns:
            None.

        """

        instance.destroyed_at = instance.updated_at = datetime.now()

        self.commit()

    def erase(self, instance: "Recyclable | Assignment") -> None:
        """Completely remove an instance from the database.

        Args:
            instance (`DeclarativeBase`): The model instance.

        Returns:
            None.
        """
        super().delete(instance)
