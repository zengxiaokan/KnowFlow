class DocumentParsingError(Exception):
    code = "parse_error"


class UnsupportedDocumentError(DocumentParsingError):
    code = "unsupported_document"


class ScannedPdfError(DocumentParsingError):
    code = "scanned_pdf"


class DocumentTooLargeError(DocumentParsingError):
    code = "document_too_large"


class RetryableProviderError(Exception):
    pass


class ProviderConfigurationError(Exception):
    pass
