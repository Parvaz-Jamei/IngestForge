class IngestForgeError(Exception):
    """Base exception for IngestForge."""


class ConfigError(IngestForgeError):
    pass


class OptionalDependencyError(IngestForgeError):
    pass


class SafeUrlError(IngestForgeError):
    pass


class FetchError(IngestForgeError):
    pass


class ValidationFailure(IngestForgeError):
    pass


class DestinationError(IngestForgeError):
    pass


class EvidenceGateError(IngestForgeError):
    pass
