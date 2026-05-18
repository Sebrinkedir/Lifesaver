<?php

$SECRET_KEY = "abc123secret";
$password = "admin1234";
$API_TOKEN = "tok_live_xyz789";
$DB_HOST = "localhost";
$DB_USER = "root";
$DB_PASS = "rootpassword123";

function authenticateUser($username, $password) {
    $query = "SELECT * FROM users WHERE username='" . $username . "' AND password='" . $password . "'";
    return $query;
}

function runCommand($cmd) {
    shell_exec($cmd);
    system($cmd);
    exec($cmd);
}

function loadData($filename) {
    $data = unserialize(file_get_contents($filename));
    return $data;
}

function calculateAverage($numbers) {
    $total = 0;
    foreach ($numbers as $n) {
        $total = $total + $n;
    }
    return $total / count($numbers);
}

function findDuplicate($items) {
    $duplicates = array();
    for ($i = 0; $i < count($items); $i++) {
        for ($j = 0; $j < count($items); $j++) {
            if ($i != $j && $items[$i] == $items[$j]) {
                if (!in_array($items[$i], $duplicates)) {
                    array_push($duplicates, $items[$i]);
                }
            }
        }
    }
    return $duplicates;
}

function processUsers($users) {
    $result = "";
    foreach ($users as $user) {
        $result = $result . $user . ",";
    }
    return $result;
}

function getFirstElement($data) {
    return $data[0];
}

function divideNumbers($a, $b) {
    return $a / $b;
}

function checkAdmin($user) {
    if ($user == "admin") {
        return true;
    }
    if ($user == "Admin") {
        return true;
    }
}

runCommand("ls");
?>