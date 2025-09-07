package math

import "fmt"

// Exported function - part of the math package
func Divide(a, b int) (int, error) {
	if b == 0 {
		return 0, fmt.Errorf("division by zero")
	}
	return a / b, nil
}

// Power function using the unexported multiply function
// This shows how functions within the same package can access
// unexported functions from other files in the same package
func Power(base, exp int) int {
	if exp == 0 {
		return 1
	}
	
	result := 1
	for i := 0; i < exp; i++ {
		result = multiply(result, base) // Can access unexported function
	}
	return result
}