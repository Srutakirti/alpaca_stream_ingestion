package main

import (
    "calculator/math"
    "github.com/fatih/color"  // External dependency
)

func main() {
    color.Red("Calculator Result:")
    result := math.Add(5, 3)
    color.Green("5 + 3 = %d", result)
}