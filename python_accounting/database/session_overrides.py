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
from typing import Any, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Mapper

from python_accounting.models import Recyclable, Recycled, Entity, Assignment
from python_accounting.exceptions import SessionEntityError

# The model type fetched by SessionOverridesMixin.get; Recyclable is the root
# mapped class that carries the primary key (id).
_O = TypeVar("_O", bound="Recyclable")


class SessionOverridesMixin:
    """
    Session overrides class.
    """

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

        return self.scalar(
            select(entity).where(entity.id == ident).execution_options(**kwargs)
        )

    def delete(self, instance) -> bool:
        """Overrides the sqlalchemy delete method to enable model recycling.

        Args:
            instance (`DeclarativeBase`): The model instance.

        Returns:
            True if successful, else False.

        Raises:
            SessionEntityError: If the instance being deleted is the session Entity.
        """

        if isinstance(instance, Assignment):
            return self.erase(instance)

        if hasattr(instance, "validate_delete"):
            instance.validate_delete(self)

        if isinstance(instance, Entity) and instance.id == self.entity.id:
            raise SessionEntityError
        instance.deleted_at = instance.updated_at = datetime.now()

        self.add(
            Recycled(
                recycled_id=instance.id,
                entity_id=self.entity.id,
            )
        )
        self.commit()
        return True

    def restore(self, instance) -> bool:
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

    def destroy(self, instance) -> bool:
        """Mark a model instance as destroyed, i.e. permanently delete.

        Args:
            instance (`DeclarativeBase`): The model instance.

        Returns:
            True.

        """

        instance.destroyed_at = instance.updated_at = datetime.now()

        self.commit()
        return True

    def erase(self, instance) -> bool:
        """Completely remove an instance from the database.

        Args:
            instance (`DeclarativeBase`): The model instance.

        Returns:
            True.

        """
        super().delete(instance)
        return True
