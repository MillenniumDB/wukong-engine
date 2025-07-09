"""Provides implementations of common design patterns.

This module defines classes that implement common software design patterns.

Classes:
    Singleton: A base class for implementing the Singleton design pattern.

Example:
    from wukong_engine.utils.patterns import Singleton

    class MySingleton(Singleton):
        pass

    my_instance = MySingleton()
"""

from typing import Any, ClassVar, TypeVar

### Singleton ###

# Type variable bound to the Singleton base class
T = TypeVar('T', bound='Singleton')


class SingletonMeta(type):
    """A metaclass that provides the Singleton design pattern.

    Ensures that only one instance of a class exists. Any attempt to
    instantiate the class will return the same existing instance.

    Attributes:
        _instances: Class attribute. Mapping of class types to their singleton instances.
    """

    _instances: ClassVar[dict[type[Any], Any]] = {}

    def __call__(cls: type[T], *args: Any, **kwargs: Any) -> T:  # pyright: ignore[reportGeneralTypeIssues]
        """Return the singleton instance of a given class.

        If an instance does not exist, it is created with the given arguments.
        Subsequent calls return the same instance.

        Args:
            *args: The positional arguments forwarded to the class constructor.
            **kwargs: The keyword arguments forwarded to the class constructor.

        Returns:
            The singleton instance of the class.
        """
        # If a specific class has already been instantiated before, return the existing instance
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class Singleton(metaclass=SingletonMeta):
    """A base class for implementing the Singleton design pattern.

    This design pattern ensures that only one instance of a class exists throughout the execution of the program.
    """
