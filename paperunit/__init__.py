"""paperunit: executable paper audits.

An audit binds each paper claim to a check a third party can re-run.  The tool
reports evidence-local verdicts (SUPPORTED / REFUTED / INCONCLUSIVE / NOT_RUN)
and never an aggregate score or ranking.
"""

__version__ = "0.4.1"

VERDICTS = ("SUPPORTED", "REFUTED", "INCONCLUSIVE", "NOT_RUN")
