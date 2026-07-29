"""Public exception hierarchy."""


class YuanshenScoreError(Exception):
    """Base class for expected user-facing errors."""


class InputFormatError(YuanshenScoreError):
    """Input does not conform to a supported schema."""


class OcrError(YuanshenScoreError):
    """Base class for OCR setup and inference failures."""


class OcrDependencyError(OcrError):
    """The optional OCR dependency is unavailable."""


class OcrModelError(OcrError):
    """The OCR model is missing or fails integrity verification."""


class OcrParseError(OcrError):
    """Recognized text cannot be converted to an artifact."""


class LowConfidenceError(OcrParseError):
    """A required OCR token does not meet the configured threshold."""
