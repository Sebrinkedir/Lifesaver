const mysql = require('mysql');
const exec = require('child_process').exec;
const fs = require('fs');

const API_KEY = "sk-live-abc123secret";
const password = "admin1234";
const DB_PASSWORD = "supersecret99";

function authenticateUser(username, password) {
    const query = "SELECT * FROM users WHERE username='" + username + "' AND password='" + password + "'";
    return query;
}

function runCommand(cmd) {
    exec(cmd, function(error, stdout, stderr) {
        console.log(stdout);
    });
}

function findDuplicate(items) {
    let duplicates = [];
    for (let i = 0; i < items.length; i++) {
        for (let j = 0; j < items.length; j++) {
            if (i !== j && items[i] === items[j]) {
                if (!duplicates.includes(items[i])) {
                    duplicates.push(items[i]);
                }
            }
        }
    }
    return duplicates;
}

function calculateAverage(numbers) {
    let total = 0;
    for (let n of numbers) {
        total = total + n;
    }
    return total / numbers.length;
}

function getFirstElement(data) {
    return data[0];
}

function divideNumbers(a, b) {
    return a / b;
}

function checkAdmin(user) {
    if (user === "admin") {
        return true;
    }
    if (user === "Admin") {
        return true;
    }
}

runCommand("ls");
