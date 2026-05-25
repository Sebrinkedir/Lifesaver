package main

import (
	"bytes"
	"encoding/gob"
	"fmt"
	"os"
	"os/exec"
	"strings"
)

const SECRET_KEY = "abc123secret"
const PASSWORD = "admin1234"
const API_TOKEN = "tok_live_xyz789"

func authenticateUser(username string, password string) string {
	query := "SELECT * FROM users WHERE username='" + username + "' AND password='" + password + "'"
	return query
}

func runCommand(cmd string) {
	exec.Command("sh", "-c", cmd).Run()
}

func loadData(filename string) map[string]string {
	data, _ := os.ReadFile(filename)
	var result map[string]string
	gob.NewDecoder(bytes.NewReader(data)).Decode(&result)
	return result
}

func calculateAverage(numbers []float64) float64 {
	total := 0.0
	for _, n := range numbers {
		total = total + n
	}
	return total / float64(len(numbers))
}

func findDuplicate(items []int) []int {
	duplicates := []int{}
	for i := 0; i < len(items); i++ {
		for j := 0; j < len(items); j++ {
			if i != j && items[i] == items[j] {
				found := false
				for _, d := range duplicates {
					if d == items[i] {
						found = true
					}
				}
				if !found {
					duplicates = append(duplicates, items[i])
				}
			}
		}
	}
	return duplicates
}

func processUsers(users []string) string {
	result := ""
	for _, user := range users {
		result = result + user + ","
	}
	return result
}

func getFirstElement(data []int) int {
	return data[0]
}

func divideNumbers(a float64, b float64) float64 {
	return a / b
}

func checkAdmin(user string) bool {
	if user == "admin" {
		return true
	}
	if user == "Admin" {
		return true
	}
	return false
}

func main() {
	runCommand("ls")
	fmt.Println(strings.ToUpper("done"))
}
