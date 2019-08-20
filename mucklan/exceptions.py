class _Base(Exception):
    def __init__(self, message: str):
        self.message = message


class NoPriceFound(Exception):
    def __init__(self, message: str):
        self.message = message

