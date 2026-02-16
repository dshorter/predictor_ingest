"""predictor_ingest — AI trend graph ingestion pipeline."""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("predictor_ingest")
except PackageNotFoundError:
    __version__ = "0.1.0b1"
