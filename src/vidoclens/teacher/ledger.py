"""Local SQLite ledger/cache. Transactions serialize concurrent budget reservations.

Never expire a reservation automatically: a crashed process may have submitted a
billable request. Reconciliation needs explicit accounting evidence.
"""

import json
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path

from vidoclens.contracts.teacher import TeacherResult
from vidoclens.teacher.requests import canonical, digest


class BudgetExceeded(RuntimeError):
    pass


class RequestInFlight(RuntimeError):
    pass


class Ledger:
    def __init__(self, path: Path, cap_micro_usd: int):
        if type(cap_micro_usd) is not int or cap_micro_usd < 0:
            raise ValueError("budget must be a nonnegative integer")
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self._transaction() as db:
            db.execute("CREATE TABLE IF NOT EXISTS budget (id INTEGER PRIMARY KEY, cap INTEGER)")
            db.execute("INSERT OR IGNORE INTO budget VALUES (1, ?)", (cap_micro_usd,))
            if db.execute("SELECT cap FROM budget WHERE id=1").fetchone()[0] != cap_micro_usd:
                raise ValueError(
                    "ledger budget is immutable; reconcile before an approved migration"
                )
            db.execute("""CREATE TABLE IF NOT EXISTS requests (
                key TEXT PRIMARY KEY, identity TEXT NOT NULL, state TEXT NOT NULL,
                result TEXT, raw TEXT, checksum TEXT)""")
            db.execute("""CREATE TABLE IF NOT EXISTS attempts (
                id TEXT PRIMARY KEY, key TEXT NOT NULL, status TEXT NOT NULL,
                reserved INTEGER NOT NULL, actual INTEGER, evidence TEXT, raw TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")

    @contextmanager
    def _transaction(self):
        db = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _summary(db):
        rows = db.execute("SELECT status, reserved, actual FROM attempts").fetchall()
        spent = sum(r["actual"] for r in rows if r["status"] == "spent")
        reserved = sum(r["reserved"] for r in rows if r["status"] == "reserved")
        uncertain = sum(r["reserved"] for r in rows if r["status"] == "uncertain_charge")
        cap = db.execute("SELECT cap FROM budget WHERE id=1").fetchone()[0]
        return {
            "cap_micro_usd": cap,
            "spent_micro_usd": spent,
            "reserved_micro_usd": reserved,
            "uncertain_micro_usd": uncertain,
            "committed_micro_usd": spent + reserved + uncertain,
            "remaining_micro_usd": cap - spent - reserved - uncertain,
            "attempts": len(rows),
            "over_cap": spent + reserved + uncertain > cap,
        }

    def summary(self):
        with self._transaction() as db:
            return self._summary(db)

    @staticmethod
    def _reserve(db, key, amount):
        if type(amount) is not int or amount <= 0:
            raise ValueError("reservation must be a positive integer")
        if amount > Ledger._summary(db)["remaining_micro_usd"]:
            raise BudgetExceeded("budget cannot cover conservative reservation")
        attempt = uuid.uuid4().hex
        db.execute(
            "INSERT INTO attempts (id,key,status,reserved) VALUES (?,?,'reserved',?)",
            (attempt, key, amount),
        )
        return attempt

    def start(self, key: str, identity: dict, amount: int) -> str:
        return self.start_many([(key, identity, amount)])[key]

    def start_many(self, entries) -> dict[str, str]:
        """An entire shard is reserved atomically before its upload."""
        if not entries or len({key for key, _, _ in entries}) != len(entries):
            raise ValueError("reservation entries must be nonempty and unique")
        with self._transaction() as db:
            attempts = {}
            for key, request_identity, amount in entries:
                if digest(request_identity) != key:
                    raise ValueError("cache identity mismatch")
                row = db.execute("SELECT state FROM requests WHERE key=?", (key,)).fetchone()
                if row and row[0] != "retryable":
                    raise RequestInFlight("request cached or active; never resubmit blindly")
                if row:
                    db.execute("UPDATE requests SET state='active' WHERE key=?", (key,))
                else:
                    db.execute(
                        "INSERT INTO requests (key,identity,state) VALUES (?,?,'active')",
                        (key, canonical(request_identity)),
                    )
                attempts[key] = self._reserve(db, key, amount)
            return attempts

    def record_raw(self, attempt: str, raw: dict):
        with self._transaction() as db:
            cursor = db.execute(
                "UPDATE attempts SET raw=? WHERE id=? AND raw IS NULL", (canonical(raw), attempt)
            )
            if cursor.rowcount != 1:
                raise ValueError("attempt missing or raw evidence already recorded")

    def reserve_retry(self, key: str, amount: int) -> str:
        with self._transaction() as db:
            row = db.execute("SELECT state FROM requests WHERE key=?", (key,)).fetchone()
            if not row or row[0] != "active":
                raise ValueError("retry requires an active request")
            if db.execute(
                "SELECT id FROM attempts WHERE key=? AND status='reserved'", (key,)
            ).fetchone():
                raise RequestInFlight("previous attempt must be settled before retry")
            return self._reserve(db, key, amount)

    @staticmethod
    def _settle(db, attempt: str, actual: int | None, evidence: str):
        if actual is not None and (type(actual) is not int or actual < 0):
            raise ValueError("actual charge must be nonnegative")
        status = "uncertain_charge" if actual is None else "released" if actual == 0 else "spent"
        cursor = db.execute(
            "UPDATE attempts SET status=?, actual=?, evidence=? WHERE id=? AND status='reserved'",
            (status, actual, evidence, attempt),
        )
        if cursor.rowcount != 1:
            raise ValueError("attempt is not reserved")

    def settle(self, attempt: str, actual: int | None, evidence: str):
        with self._transaction() as db:
            self._settle(db, attempt, actual, evidence)

    def finish(self, key: str, result: TeacherResult, raw: dict, *, attempt=None, actual=None):
        result = TeacherResult.model_validate(result.model_dump())
        if result.request_key != key:
            raise ValueError("result belongs to another request")
        packed = {"result": result.model_dump(mode="json"), "raw": raw}
        with self._transaction() as db:
            if attempt is not None:
                row = db.execute("SELECT key FROM attempts WHERE id=?", (attempt,)).fetchone()
                if not row or row[0] != key:
                    raise ValueError("attempt belongs to another request")
                self._settle(db, attempt, actual, result.error_code or result.status)
            cursor = db.execute(
                "UPDATE requests SET state='complete',result=?,raw=?,checksum=? "
                "WHERE key=? AND state='active'",
                (canonical(packed["result"]), canonical(raw), digest(packed), key),
            )
            if cursor.rowcount != 1:
                raise ValueError("request is not active")

    def cached(self, key: str) -> TeacherResult | None:
        with self._transaction() as db:
            row = db.execute("SELECT * FROM requests WHERE key=?", (key,)).fetchone()
            if row is None:
                return None
            if row["state"] == "retryable":
                return None
            if row["state"] != "complete":
                raise RequestInFlight("unfinished submission requires reconciliation")
            packed = {"result": json.loads(row["result"]), "raw": json.loads(row["raw"])}
            if digest(packed) != row["checksum"] or digest(json.loads(row["identity"])) != key:
                raise ValueError("cache checksum mismatch")
            result = TeacherResult.model_validate(packed["result"])
            if result.request_key != key:
                raise ValueError("cache key mismatch")
            return result

    def allow_batch_resubmit(self, key: str):
        """Only reconciled, provably unexecuted Batch requests can be reopened."""
        with self._transaction() as db:
            row = db.execute("SELECT state,result FROM requests WHERE key=?", (key,)).fetchone()
            if not row or row[0] != "complete":
                raise ValueError("request must first be reconciled")
            result = TeacherResult.model_validate_json(row[1])
            if result.error_code != "batch_not_executed":
                raise ValueError("only documented unexecuted requests may be resubmitted")
            if db.execute(
                "SELECT id FROM attempts WHERE key=? AND status != 'released'", (key,)
            ).fetchone():
                raise ValueError("request has unresolved or spent attempts")
            db.execute("UPDATE requests SET state='retryable' WHERE key=?", (key,))

    def reconcile_charge(self, attempt: str, actual_micro_usd: int, evidence: str):
        """Explicit reconciliation only; cannot overwrite known spend or erase history."""
        if type(actual_micro_usd) is not int or actual_micro_usd < 0 or not evidence.strip():
            raise ValueError("reconciliation requires nonnegative charge and evidence")
        with self._transaction() as db:
            row = db.execute(
                "SELECT status,evidence FROM attempts WHERE id=?", (attempt,)
            ).fetchone()
            if not row or row[0] not in {"reserved", "uncertain_charge"}:
                raise ValueError("only unresolved charges may be reconciled")
            db.execute(
                "UPDATE attempts SET status=?,actual=?,evidence=? WHERE id=?",
                (
                    "spent" if actual_micro_usd else "released",
                    actual_micro_usd,
                    canonical({"previous": row[1], "reconciliation": evidence}),
                    attempt,
                ),
            )

    def validate_attempt_mapping(self, attempts: dict[str, str]):
        if len(set(attempts.values())) != len(attempts):
            raise ValueError("duplicate attempt identifiers")
        with self._transaction() as db:
            for key, attempt in attempts.items():
                row = db.execute("SELECT key FROM attempts WHERE id=?", (attempt,)).fetchone()
                if row is None or row[0] != key:
                    raise ValueError("attempt mapping does not match ledger")

    def unresolved(self):
        with self._transaction() as db:
            return [
                dict(r)
                for r in db.execute(
                    "SELECT id,key,status,reserved FROM attempts "
                    "WHERE status IN ('reserved','uncertain_charge') ORDER BY created_at,id"
                )
            ]
