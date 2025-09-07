package math

// Exported constant (starts with capital letter)
const PI = 3.14159

// Exported functions (start with capital letters)
func Add(a, b int) int {
	return a + b
}

func Subtract(a, b int) int {
	return a - b
}

func Multiply(a, b int) int {
	return multiply(a, b) // calling unexported function
}

// Unexported function (starts with lowercase letter)
// This can only be used within the math package
func multiply(a, b int) int {
	return a * b
}

// unexported function for demonstration
func square(n int) int {
	return n * n
}

// Exported wrapper function that uses unexported function
func GetSquare(n int) int {
	return square(n)
}