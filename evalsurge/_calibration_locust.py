"""Private fixed timing-only wrapper; imported only in the owned Locust child."""

import os

from gevent.monkey import get_original

import benchmark_agents.locustfile as production

AgentUser = production.AgentUser
mode = os.environ["EVALSURGE_CALIBRATION_MODE"]
if mode not in {
    "native",
    "native_fsync_delay",
    "fail_start_before_write",
    "fail_completion_before_write",
}:
    raise ValueError("Unsupported internal calibration mode")

if mode == "native_fsync_delay":
    native_identity = get_original("_thread", "get_ident")
    native_sleep = get_original("time", "sleep")
    hub_identity = native_identity()
    original_fsync = os.fsync

    def delayed_native_fsync(descriptor: int) -> None:
        """Inject five ms only into native journal sync, then perform actual fsync.

        Args:
            descriptor: Descriptor owned by the production journal writer.

        Raises:
            OSError: Actual native fsync fails.

        This process-local disk control is never an agent/inference substitute.
        Atomic result writes on the hub receive no injected delay.
        """
        if native_identity() != hub_identity:
            native_sleep(0.005)
        original_fsync(descriptor)

    os.fsync = delayed_native_fsync
elif mode.startswith("fail_"):
    original_write = production.CooperativeJournal._write_native

    def failed_native_write(self: production.CooperativeJournal, event: dict) -> float:
        """Inject a labeled native storage failure before START or completion write.

        Args:
            self: Native journal owner; the load engine remains unchanged.
            event: Fixed started/completed lifecycle event.

        Returns:
            Actual serialization/write/fsync duration for unaffected events.

        Raises:
            OSError: The selected native storage-fault probe is reached.
        """
        if (mode == "fail_start_before_write" and event["kind"] == "started") or (
            mode == "fail_completion_before_write" and event["kind"] == "completed"
        ):
            raise OSError("Controlled non-inference journal fault")
        return original_write(self, event)

    production.CooperativeJournal._write_native = failed_native_write
