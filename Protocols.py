from typing import Protocol
from enum import Flag

class BackendSignal(Flag):

    UNDEFINED = 0
    RELAXATION_1 = 1
    RELAXATION_2 = 2
    BLINK = 4
    @classmethod
    def _missing_(cls, value):
        try:
            return super()._missing_(value)
        except ValueError:
            return cls.UNDEFINED

class ListenerI(Protocol):
    ...
class BackendI(Protocol):

    GUI: ListenerI
    def __enter__(self) -> bool:

        ...

    def __exit__(self, exc_type, exc_val, tb) -> None:
        ...

class MessengerI(Protocol):
    """Protocol followed by the server the GUI is using to sent signals to physical implementations connected
    """
    def send_signal(self):
        ...

class ListenerI(Protocol):
    """Protocol followed by the GUI to receive signals from the Backend
    """
    backend: BackendI
    server: MessengerI|None
    def send_signal(self, signal: BackendSignal):
        ...