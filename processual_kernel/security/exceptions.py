class CryptoError(Exception):
    pass


class EncryptionError(CryptoError):
    pass


class DecryptionError(CryptoError):
    pass


class KeyError(CryptoError):
    pass
