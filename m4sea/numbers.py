"""Shared numeric input parsing, without restrictions on exponent notation."""
import math
from typing import Any


def parse_number(value: Any) -> float | None:
    """Parse optional finite numbers; empty inputs remain unknown, never zero."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError(f'Valor numérico inválido: {value!r}')
    try:
        number = float(value)
    except (ValueError, OverflowError) as exc:
        raise ValueError(f'Valor numérico inválido: {value!r}') from exc
    if not math.isfinite(number):
        raise ValueError('Valor numérico finito obrigatório.')
    return number


def normalize_parameters(data: Any) -> Any:
    """Copy parameter values to floats, including XYZ; preserve IDs and sources.

    Only metadata objects containing ``value`` are numeric parameters. Other
    JSON numbers keep their native numeric types and unrelated text is untouched.
    """
    if isinstance(data, list):
        return [normalize_parameters(item) for item in data]
    if not isinstance(data, dict):
        return data
    result = {key: normalize_parameters(value) for key, value in data.items()}
    if 'value' in result:
        value = result['value']
        result['value'] = ([parse_number(item) for item in value]
                           if isinstance(value, list) else parse_number(value))
    return result
