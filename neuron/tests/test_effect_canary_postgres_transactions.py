"""Controlled-driver regressions for PostgreSQL transaction ownership.

These tests exercise repository methods without a PostgreSQL service. They prove
transaction-control calls and coordinator recovery behavior only; they do not
prove durable persistence, concurrency, or restart recovery.
"""
from __future__ import annotations

import copy
import hashlib
import time
import uuid
from unittest.mock import patch

import pytest

from neuron.effect_canary import (
    ApprovedAction,
    AttenuatedCapability,
    EffectCoordinator,
    EffectStatus,
    PostgresAuthorityRepository,
    ProviderEffectContract,
    ResolvedImplementation,
)


class DriverFailure(RuntimeError):
    pass


class _State:
    def __init__(self, action: ApprovedAction | None = None):
        self.authorities = {}
        self.operations = {}
        self.observations = {}
        self.commit_failures_remaining = 0
        if action is not None:
            self.authorities[action.principal_id] = {
                "task_id": action.task_id,
                "target": action.target,
                "implementation_digest": action.implementation.digest,
                "object_prefix": action.principal_id + "/",
                "budget_limit": 10,
                "max_action_cost": 5,
                "budget_reserved": action.cost_units,
                "budget_spent": 0,
                "policy_revision": action.policy_revision,
                "authority_epoch": action.authority_epoch,
                "expires_at": action.expires_at,
                "revoked": False,
            }
            self.operations[action.operation_id] = {
                "action_digest": action.action_digest,
                "status": "pending",
                "cost_units": action.cost_units,
                "receipt": None,
            }


class _Connection:
    def __init__(self, state: _State, *, execute_error=None, fetchone_error=None,
                 rollback_error=None, commit_error=None):
        self.state = state
        self.authorities = copy.deepcopy(state.authorities)
        self.operations = copy.deepcopy(state.operations)
        self.observations = copy.deepcopy(state.observations)
        self.execute_error = execute_error
        self.fetchone_error = fetchone_error
        self.rollback_error = rollback_error
        self.commit_error = commit_error
        self.committed_effect_update = False
        self.commit_calls = 0
        self.rollback_calls = 0
        self.close_calls = 0

    def cursor(self):
        return _Cursor(self)

    def commit(self):
        self.commit_calls += 1
        if self.commit_error is not None:
            raise self.commit_error
        if self.committed_effect_update and self.state.commit_failures_remaining:
            self.state.commit_failures_remaining -= 1
            raise DriverFailure("synthetic database commit failure after provider effect")
        self.state.authorities = copy.deepcopy(self.authorities)
        self.state.operations = copy.deepcopy(self.operations)
        self.state.observations = copy.deepcopy(self.observations)

    def rollback(self):
        self.rollback_calls += 1
        if self.rollback_error is not None:
            raise self.rollback_error

    def close(self):
        self.close_calls += 1


class _Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.rowcount = -1
        self._row = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        if self.connection.execute_error is not None:
            raise self.connection.execute_error
        sql = " ".join(sql.split())
        state = self.connection
        if sql.startswith("SELECT action_digest,status,cost_units FROM vams_effect_operations"):
            row = state.operations.get(params[0])
            self._row = None if row is None else (row["action_digest"], row["status"], row["cost_units"])
        elif sql.startswith("SELECT task_id,target,implementation_digest,object_prefix,budget_limit,max_action_cost,budget_reserved,budget_spent,policy_revision,authority_epoch,expires_at,revoked FROM vams_effect_authority"):
            row = state.authorities.get(params[0])
            self._row = None if row is None else tuple(row[key] for key in (
                "task_id", "target", "implementation_digest", "object_prefix", "budget_limit",
                "max_action_cost", "budget_reserved", "budget_spent", "policy_revision",
                "authority_epoch", "expires_at", "revoked"))
        elif sql.startswith("SELECT task_id,target,implementation_digest,object_prefix,max_action_cost,budget_reserved,policy_revision,authority_epoch,expires_at,revoked FROM vams_effect_authority"):
            row = state.authorities.get(params[0])
            self._row = None if row is None else tuple(row[key] for key in (
                "task_id", "target", "implementation_digest", "object_prefix", "max_action_cost",
                "budget_reserved", "policy_revision", "authority_epoch", "expires_at", "revoked"))
        elif sql.startswith("UPDATE vams_effect_authority SET budget_reserved=budget_reserved+"):
            row = state.authorities[params[1]]
            row["budget_reserved"] += params[0]
            self.rowcount = 1
        elif sql.startswith("INSERT INTO vams_effect_operations"):
            operation_id, action_digest, _action_json, cost_units = params[:4]
            state.operations[operation_id] = {
                "action_digest": action_digest,
                "status": "pending",
                "cost_units": cost_units,
                "receipt": None,
            }
            self.rowcount = 1
        elif sql.startswith("UPDATE vams_effect_authority SET budget_reserved=budget_reserved-"):
            reserved_cost, spent_cost, principal_id = params
            row = state.authorities[principal_id]
            row["budget_reserved"] -= reserved_cost
            row["budget_spent"] += spent_cost
            self.rowcount = 1
        elif sql.startswith("UPDATE vams_effect_operations SET status='committed'"):
            receipt, _updated_at, operation_id = params
            row = state.operations[operation_id]
            row["status"] = "committed"
            row["receipt"] = receipt
            self.connection.committed_effect_update = True
            self.rowcount = 1
        elif sql.startswith("UPDATE vams_effect_operations SET status='indeterminate'"):
            _updated_at, operation_id = params
            row = state.operations.get(operation_id)
            self.rowcount = 0
            if row is not None and row["status"] == "pending":
                row["status"] = "indeterminate"
                self.rowcount = 1
        elif sql.startswith("INSERT INTO vams_effect_observations"):
            self.rowcount = 1
        elif sql.startswith("INSERT INTO vams_effect_authority"):
            self.rowcount = 1
        else:
            raise AssertionError("unexpected SQL in controlled test: " + sql)

    def fetchone(self):
        if self.connection.fetchone_error is not None:
            raise self.connection.fetchone_error
        return self._row


def _action(content=b"synthetic object", operation_id=None):
    implementation_digest = hashlib.sha256(b"synthetic implementation").hexdigest()
    return ApprovedAction(
        principal_id="principal-a",
        task_id="task-a",
        operation_id=operation_id or str(uuid.uuid4()),
        target="local-object-v1",
        implementation=ResolvedImplementation("local-object-provider", "1.0.0", implementation_digest),
        object_key="principal-a/task-a/object-1",
        content_hash=hashlib.sha256(content).hexdigest(),
        cost_units=1,
        policy_revision=4,
        authority_epoch=7,
        expires_at=int(time.time()) + 300,
    )


def _capability():
    return AttenuatedCapability(
        principal_id="principal-a",
        task_id="task-a",
        target="local-object-v1",
        implementation_digest=hashlib.sha256(b"synthetic implementation").hexdigest(),
        max_cost_units=2,
        policy_revision=4,
        authority_epoch=7,
        expires_at=int(time.time()) + 300,
        object_prefix="principal-a/",
    )


def _repository(connection):
    repository = PostgresAuthorityRepository("postgresql://controlled-test.invalid/vams")
    return repository, patch.object(repository, "_connect", return_value=connection)


def test_successful_repository_write_commits_and_closes_connection():
    state = _State()
    connection = _Connection(state)
    repository, connect = _repository(connection)
    with connect:
        repository.provision_capability(_capability(), budget_units=5)
    assert connection.commit_calls == 1
    assert connection.rollback_calls == 0
    assert connection.close_calls == 1


def test_cursor_execute_failure_rolls_back_and_closes_connection():
    state = _State()
    failure = DriverFailure("synthetic cursor execute failure")
    connection = _Connection(state, execute_error=failure)
    repository, connect = _repository(connection)
    with connect, pytest.raises(DriverFailure, match="cursor execute failure"):
        repository.provision_capability(_capability(), budget_units=5)
    assert connection.commit_calls == 0
    assert connection.rollback_calls == 1
    assert connection.close_calls == 1


def test_cursor_fetch_failure_rolls_back_and_closes_connection():
    action = _action()
    state = _State(action)
    failure = DriverFailure("synthetic cursor fetch failure")
    connection = _Connection(state, fetchone_error=failure)
    repository, connect = _repository(connection)
    with connect, pytest.raises(DriverFailure, match="cursor fetch failure"):
        repository.commit_if_current(action, lambda: "must-not-run")
    assert connection.commit_calls == 0
    assert connection.rollback_calls == 1
    assert connection.close_calls == 1


def test_commit_failure_after_effect_never_returns_committed_and_closes():
    action = _action()
    state = _State(action)
    failure = DriverFailure("synthetic commit failure")
    connection = _Connection(state, commit_error=failure)
    repository, connect = _repository(connection)
    effects = []
    with connect, pytest.raises(DriverFailure, match="commit failure"):
        repository.commit_if_current(action, lambda: effects.append(action.operation_id) or "receipt")
    assert effects == [action.operation_id]
    assert connection.rollback_calls == 1
    assert connection.close_calls == 1
    assert state.operations[action.operation_id]["status"] == "pending"
    # An exception, rather than a returned outcome, is the only valid result
    # when the provider effect happened but its database commit failed.


def test_rollback_failure_does_not_skip_connection_cleanup_or_hide_body_error():
    state = _State()
    body_failure = DriverFailure("synthetic cursor execute failure")
    rollback_failure = DriverFailure("synthetic rollback failure")
    connection = _Connection(state, execute_error=body_failure, rollback_error=rollback_failure)
    repository, connect = _repository(connection)
    with connect, pytest.raises(DriverFailure, match="cursor execute failure") as raised:
        repository.provision_capability(_capability(), budget_units=5)
    assert raised.value is body_failure
    assert connection.rollback_calls == 1
    assert connection.close_calls == 1


def test_connection_closes_when_commit_fails():
    state = _State()
    connection = _Connection(state, commit_error=DriverFailure("synthetic commit failure"))
    repository, connect = _repository(connection)
    with connect, pytest.raises(DriverFailure, match="commit failure"):
        repository.provision_capability(_capability(), budget_units=5)
    assert connection.rollback_calls == 1
    assert connection.close_calls == 1


def test_coordinator_recovers_provider_effect_after_database_commit_failure_by_same_operation_id(monkeypatch):
    content = b"synthetic object"
    action = _action(content)
    state = _State(action)
    state.operations.clear()
    state.authorities[action.principal_id]["budget_reserved"] = 0
    state.commit_failures_remaining = 1
    connections = []

    def connect():
        connection = _Connection(state)
        connections.append(connection)
        return connection

    repository = PostgresAuthorityRepository("postgresql://controlled-test.invalid/vams")
    repository._connect = connect

    class IdempotentProvider:
        contract = ProviderEffectContract("controlled-provider", True, True, True)

        def __init__(self):
            self.effects = {}
            self.operation_ids = []

        def put(self, requested_action, requested_content):
            assert requested_action.operation_id == action.operation_id
            assert requested_content == content
            self.operation_ids.append(requested_action.operation_id)
            previous = self.effects.get(requested_action.operation_id)
            if previous is not None:
                assert previous[0] == requested_action.action_digest
                assert previous[1] == requested_action.content_hash
                return previous[2]
            receipt = "synthetic-provider-receipt"
            self.effects[requested_action.operation_id] = (
                requested_action.action_digest,
                requested_action.content_hash,
                receipt,
            )
            return receipt

        def lookup(self, operation_id):
            effect = self.effects.get(operation_id)
            if effect is None:
                return None
            return {"action_digest": effect[0], "content_hash": effect[1], "receipt": effect[2]}

        def observe(self, operation_id):
            effect = self.effects.get(operation_id)
            if effect is None:
                return None
            return {"object_hash": effect[1]}

    monkeypatch.setenv("VAMS_ENV", "test")
    provider = IdempotentProvider()
    outcome = EffectCoordinator(repository, provider).execute(action, content)

    assert outcome.status is EffectStatus.COMMITTED
    assert outcome.operation_id == action.operation_id
    assert provider.operation_ids == [action.operation_id, action.operation_id]
    assert state.operations[action.operation_id]["status"] == "committed"
    assert state.authorities[action.principal_id]["budget_reserved"] == 0
    assert state.authorities[action.principal_id]["budget_spent"] == action.cost_units
    assert len(connections) == 5
    assert all(connection.close_calls == 1 for connection in connections)
    assert connections[1].rollback_calls == 1
