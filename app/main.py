def add(a: int, b: int) -> int:
    if not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
        raise TypeError('Inputs must be int or float')
    return a + b