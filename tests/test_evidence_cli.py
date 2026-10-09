"""Pure CLI presentation checks over metadata; no target or judge execution."""

from evalsurge.cli import _summary


def test_summary_separates_evidence_configuration_from_observations(capsys):
    """Only fixed state vocabulary is printed, never protected guidance/content."""
    _summary(
        {
            "run": {
                "evidence": {
                    "load_measurements": {"configured": True, "state": "observed"},
                    "answer_evaluation": {"configured": False, "state": "off"},
                    "internal_profiling": {"configured": True, "state": "unavailable"},
                    "trace_aware_evaluation": {
                        "configured": "private-profile",
                        "state": "private-content",
                        "guidance": "private-token",
                    },
                }
            }
        }
    )
    output = capsys.readouterr().out
    assert "Load measurements" in output
    assert "Captured-answer judging" in output
    assert "Internal profiling" in output
    assert "Trace-aware judging" in output
    assert "unknown" in output
    assert "Configured is not verified" in output
    assert "private" not in output


def test_old_report_summary_does_not_invent_evidence_states(capsys):
    """Old documents remain usable without pretending selection was recorded."""
    _summary({"run": {}})
    output = capsys.readouterr().out
    assert "Evidence capability" not in output
    assert "Performance metrics: unavailable" in output
