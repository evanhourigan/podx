#!/usr/bin/env python3
"""
Pipeline data validation utilities.
"""

from functools import wraps
from typing import Any, Callable, Dict, Type, TypeVar, Union

from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from .errors import ValidationError
from .logging import get_logger

logger = get_logger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def validate_input(schema: Type[BaseModel]) -> Callable[[F], F]:
    """
    Decorator to validate function input against a Pydantic schema.

    Args:
        schema: Pydantic model class to validate against
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Assume first argument is the data to validate
            if args:
                data = args[0]
                try:
                    validated = schema.model_validate(data)
                    logger.debug("Input validation passed", schema=schema.__name__)
                    return func(validated.model_dump(), *args[1:], **kwargs)
                except PydanticValidationError as e:
                    logger.error(
                        "Input validation failed",
                        schema=schema.__name__,
                        errors=e.errors(),
                    )
                    raise ValidationError(f"Invalid input for {schema.__name__}: {e}")
            return func(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


def validate_output(schema: Type[BaseModel]) -> Callable[[F], F]:
    """
    Decorator to validate function output against a Pydantic schema.

    Args:
        schema: Pydantic model class to validate against
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = func(*args, **kwargs)
            try:
                _validated = schema.model_validate(result)  # Validate but don't use
                logger.debug("Output validation passed", schema=schema.__name__)
                return result  # Return original result, not validated model
            except PydanticValidationError as e:
                logger.error(
                    "Output validation failed",
                    schema=schema.__name__,
                    errors=e.errors(),
                )
                raise ValidationError(f"Invalid output for {schema.__name__}: {e}")

        return wrapper  # type: ignore[return-value]

    return decorator


def validate_pipeline_step(
    input_schema: Type[BaseModel], output_schema: Type[BaseModel]
) -> Callable[[F], F]:
    """
    Decorator to validate both input and output of a pipeline step.

    Args:
        input_schema: Pydantic model for input validation
        output_schema: Pydantic model for output validation
    """

    def decorator(func: F) -> F:
        return validate_output(output_schema)(validate_input(input_schema)(func))

    return decorator


def validate_pipeline_compatibility(
    data: Dict[str, Any], expected_schema: Type[BaseModel]
) -> bool:
    """
    Check if data is compatible with expected schema without raising exceptions.

    Args:
        data: Data to validate
        expected_schema: Expected Pydantic schema

    Returns:
        True if compatible, False otherwise
    """
    try:
        expected_schema.model_validate(data)
        return True
    except PydanticValidationError:
        return False


def safe_parse(data: Dict[str, Any], schema: Type[BaseModel]) -> Union[BaseModel, None]:
    """
    Safely parse data with schema, returning None on validation errors.

    Args:
        data: Data to parse
        schema: Pydantic schema

    Returns:
        Parsed model instance or None if validation fails
    """
    try:
        return schema.model_validate(data)
    except PydanticValidationError as e:
        logger.debug("Validation failed", schema=schema.__name__, errors=e.errors())
        return None
