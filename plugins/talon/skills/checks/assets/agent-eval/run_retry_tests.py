"""Run one isolated service variant and observe persisted order transitions."""

from collections import defaultdict
from contextlib import closing
import json
from pathlib import Path
import resource
import sqlite3
import sys
import unittest


def one_order(call):
    return call["after"] == [(call["returned"], call["key"], call["item"])]


def observed_scenarios(calls):
    scenarios = set()
    for first, second in zip(calls, calls[1:]):
        if (first["store"] != second["store"] or first["before"] != []
                or second["before"] != first["after"] or first["item"] != second["item"]
                or second["raised"]):
            continue
        if (not first["raised"] and one_order(first) and first["key"] != second["key"]
                and second["after"] == first["after"] + [(second["returned"], second["key"], second["item"])]
                and first["returned"] != second["returned"]):
            scenarios.add("distinct_keys")
        if (first["key"] != second["key"] or not first["raised"] or not first["lost_ack"]
                or first["after"] != [(first["ack_id"], first["key"], first["item"])]
                or first["ack_rows"] != first["after"]):
            continue
        if second["after"] == first["after"] and second["returned"] == first["ack_id"]:
            scenarios.add("retry_kept_one")
        if second["after"] == first["after"] and second["returned"] != first["ack_id"]:
            scenarios.add("wrong_response_id")
        if (second["after"] == [(first["ack_id"] + 1000, second["key"], second["item"])]
                and second["returned"] == first["ack_id"]):
            scenarios.add("replaced_row_id")
        if (second["after"] == first["after"] + [(second["returned"], second["key"], second["item"])]
                and second["returned"] != first["ack_id"]):
            scenarios.add("retry_duplicate")
    return scenarios


class RetryResult(unittest.TestResult):
    def __init__(self):
        super().__init__()
        self.test_ids = []
        self.passed_ids = []
        self.failed_ids = []
        self.current_id = None

    def startTest(self, test):
        super().startTest(test)
        self.current_id = test.id()
        self.test_ids.append(self.current_id)

    def stopTest(self, test):
        self.current_id = None
        super().stopTest(test)

    def addSuccess(self, test):
        self.passed_ids.append(test.id())
        super().addSuccess(test)

    def addFailure(self, test, err):
        self.failed_ids.append(test.id())
        super().addFailure(test, err)

    def addSubTest(self, test, subtest, err):
        if err is not None and issubclass(err[0], test.failureException):
            self.failed_ids.append(test.id())
        super().addSubTest(test, subtest, err)


def change_retry_result(control, store, order_id):
    if control == "wrong_response_id":
        return order_id + 1000
    if control == "replaced_row_id":
        with closing(sqlite3.connect(store)) as connection, connection:
            connection.execute("UPDATE orders SET id = ? WHERE id = ?", (order_id + 1000, order_id))
    return order_id


def observe_service(service, result, observations, control):
    create_store = service.create_store
    submit_order = service.submit_order
    read_orders = service.read_orders
    initialized = {}
    data = Path.cwd().resolve()

    def create(path):
        store = Path(path).resolve()
        fresh = store.is_relative_to(data) and (not store.exists() or store.stat().st_size == 0)
        create_store(path)
        if fresh and read_orders(store) == []:
            initialized[store] = result.current_id

    def submit(path, operation_key, item, *, acknowledge=None):
        store = Path(path).resolve()
        if result.current_id is None or initialized.get(store) != result.current_id:
            return submit_order(path, operation_key, item, acknowledge=acknowledge)
        before = read_orders(store)
        details = dict(store=store, key=operation_key, item=item, before=before,
                       raised=False, lost_ack=False, returned=None, ack_id=None, ack_rows=None)

        def observe_ack(order_id):
            details.update(ack_id=order_id, ack_rows=read_orders(store))
            try:
                return acknowledge(order_id)
            except Exception:
                details["lost_ack"] = True
                raise

        try:
            returned = submit_order(path, operation_key, item,
                                    acknowledge=observe_ack if acknowledge is not None else None)
            if control != "none" and any(key == operation_key for _, key, _ in before):
                returned = change_retry_result(control, store, returned)
            details["returned"] = returned
            return returned
        except Exception:
            details["raised"] = True
            raise
        finally:
            details["after"] = read_orders(store)
            observations[result.current_id].append(details)

    service.create_store = create
    service.submit_order = submit


def main():
    resource.setrlimit(resource.RLIMIT_CPU, (8, 8))
    resource.setrlimit(resource.RLIMIT_FSIZE, (4 * 1024 * 1024, 4 * 1024 * 1024))
    inputs = str(Path(__file__).parent)
    report_path = Path(sys.argv[1])
    control = sys.argv[2]
    sys.path.insert(0, inputs)
    import retry_fixture

    result = RetryResult()
    observations = defaultdict(list)
    observe_service(retry_fixture, result, observations, control)
    suite = unittest.TestLoader().discover(inputs, pattern="test_retry.py")
    suite.run(result)
    report = {
        "schema": 1,
        "tests": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped) + len(result.expectedFailures) + len(result.unexpectedSuccesses),
        "test_ids": result.test_ids,
        "passed_ids": result.passed_ids,
        "failed_ids": result.failed_ids,
        "retry_duplicate": [],
        "retry_kept_one": [],
        "distinct_keys": [],
        "wrong_response_id": [],
        "replaced_row_id": [],
    }
    for test_id, calls in observations.items():
        for scenario in observed_scenarios(calls):
            report[scenario].append(test_id)
    report_path.write_text(json.dumps(report), encoding="utf-8")


if __name__ == "__main__":
    main()
