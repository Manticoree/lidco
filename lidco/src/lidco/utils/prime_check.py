"""Utility functions for prime number checking."""


def is_prime(n: int) -> bool:
    """
    Check if a number is prime.

    Args:
        n: The number to check for primality.

    Returns:
        True if the number is prime, False otherwise.

    Examples:
        >>> is_prime(2)
        True
        >>> is_prime(17)
        True
        >>> is_prime(15)
        False
        >>> is_prime(1)
        False
        >>> is_prime(0)
        False
        >>> is_prime(-5)
        False
    """
    if n < 2:
        return False
    if n == 2:
        return True
    if n % 2 == 0:
        return False

    # Check divisors up to sqrt(n)
    limit = int(n ** 0.5) + 1
    for i in range(3, limit, 2):
        if n % i == 0:
            return False

    return True
