# tests/test_config.py
# Copyright (C) 2024 - 2028 the PythonAccounting authors and contributors
# <see AUTHORS file>
#
# This module is part of PythonAccounting and is released under
# the MIT License: https://www.opensource.org/licenses/mit-license.php

import pytest

from python_accounting.config import Config, default_configuration


@pytest.fixture
def fresh_config():
    """A Config instance isolated from the global config singleton."""
    return Config(config_file=default_configuration)


def test_configure_dates_writes_to_dates(fresh_config):
    """configure_dates must update the dates dictionary."""

    fresh_config.configure_dates(short="%d/%m/%Y", long="%d %B %Y")

    assert fresh_config.dates["short"] == "%d/%m/%Y"
    assert fresh_config.dates["long"] == "%d %B %Y"


def test_configure_dates_does_not_pollute_hashing(fresh_config):
    """The hashing dictionary only ever holds salt and algorithm."""

    fresh_config.configure_dates(short="%d/%m/%Y", long="%d %B %Y")

    assert "short" not in fresh_config.hashing
    assert "long" not in fresh_config.hashing


def test_configure_dates_restores_documented_defaults(fresh_config):
    """configure_dates with no arguments restores the documented defaults."""

    fresh_config.dates["short"] = "%d/%m/%Y"
    fresh_config.dates["long"] = "%d %B %Y"

    fresh_config.configure_dates()

    assert fresh_config.dates["short"] == "%Y-%m-%d"
    assert fresh_config.dates["long"] == "%d, %b %Y"


def test_configure_hashing_only_touches_hashing(fresh_config):
    """configure_hashing must not leak keys into hashing or clobber dates."""

    dates_before = dict(fresh_config.dates)

    fresh_config.configure_hashing(salt="s", algorithm="md5")

    assert fresh_config.hashing["salt"] == "s"
    assert fresh_config.hashing["algorithm"] == "md5"
    assert "short" not in fresh_config.hashing
    assert "long" not in fresh_config.hashing
    assert fresh_config.dates == dates_before
