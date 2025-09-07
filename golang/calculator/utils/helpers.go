package utils

import "fmt"

// Exported function
func IsEven(n int) bool {
	return n%2 == 0
}

// Exported function
func IsOdd(n int) bool {
	return !IsEven(n)
}

// Exported function that uses fmt package
func PrintInfo(message string) {
	fmt.Printf("[INFO] %s\n", message)
}

// unexported variable
var debugMode = false

// Exported function to access unexported variable
func SetDebugMode(mode bool) {
	debugMode = mode
}

func GetDebugMode() bool {
	return debugMode
}