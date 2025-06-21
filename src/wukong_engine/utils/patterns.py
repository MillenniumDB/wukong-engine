from typing import Any, ClassVar, TypeVar

### Singleton ###

# Type variable bound to the Singleton base class
T = TypeVar('T', bound='Singleton')


class SingletonMeta(type):
    """
    Meta class to adapt the Singleton design pattern.
    """

    _instances: ClassVar[dict[type[Any], Any]] = {}

    def __call__(cls: type[T], *args: Any, **kwargs: Any) -> T:  # pyright: ignore[reportGeneralTypeIssues]
        # If a specific class has already been instantiated before, return the existing instance
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class Singleton(metaclass=SingletonMeta):
    pass
