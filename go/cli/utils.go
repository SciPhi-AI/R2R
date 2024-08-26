package main

import (
	"fmt"
	"time"

	"github.com/spf13/cobra"
)

func withTimer(f func(*cobra.Command, []string)) func(*cobra.Command, []string) {
	return func(cmd *cobra.Command, args []string) {
		start := time.Now()
		f(cmd, args)
		duration := time.Since(start)
		fmt.Printf("Time taken: %.2f seconds\n", duration.Seconds())
	}
}
