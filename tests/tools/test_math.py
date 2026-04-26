from arachne.tools.math.calculator import evaluate_math


def test_evaluate_math_basic_arithmetic():
    """Test basic arithmetic operations."""
    assert evaluate_math("2 + 2") == "4"
    assert evaluate_math("10 - 5") == "5"
    assert evaluate_math("3 * 4") == "12"
    assert evaluate_math("15 / 3") == "5.0"
    assert evaluate_math("10 // 3") == "3"
    assert evaluate_math("10 % 3") == "1"
    assert evaluate_math("2 ** 3") == "8"
    assert evaluate_math("-5 + 10") == "5"


def test_evaluate_math_functions():
    """Test supported math functions."""
    assert evaluate_math("math.sqrt(16)") == "4.0"
    assert evaluate_math("abs(-10)") == "10"
    assert evaluate_math("max(1, 5, 3)") == "5"
    assert evaluate_math("min(1, 5, 3)") == "1"
    assert evaluate_math("round(3.14159, 2)") == "3.14"


def test_evaluate_math_complex_expression():
    """Test combination of operations."""
    assert evaluate_math("round(math.sqrt(16) * 2.5 + max(1, 2), 1)") == "12.0"


def test_evaluate_math_zero_division():
    """Test division by zero handling."""
    result = evaluate_math("10 / 0")
    assert "Error evaluating expression" in result
    assert "division by zero" in result


def test_evaluate_math_unsupported_function():
    """Test that unauthorized functions are blocked."""
    result = evaluate_math("os.system('echo 1')")
    assert "Error evaluating expression" in result


def test_evaluate_math_invalid_syntax():
    """Test syntax error handling."""
    result = evaluate_math("2 + * 3")
    assert "Error evaluating expression" in result
