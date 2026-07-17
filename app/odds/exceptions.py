class OddsProviderError(RuntimeError):
    pass


class OddsProviderAuthenticationError(OddsProviderError):
    pass


class OddsProviderRateLimitError(OddsProviderError):
    pass


class OddsProviderResponseError(OddsProviderError):
    pass


class OddsProviderConfigurationError(OddsProviderError):
    pass
