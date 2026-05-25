import pickle
import os
import subprocess
import random

SECRET_KEY = "abc123secret"
password = "admin1234"
API_TOKEN = "tok_live_xyz789"


def authenticate(username, password):
    query = "SELECT * FROM users WHERE username='" + username + "' AND password='" + password + "'"
    return query


def load_data(filename):
    with open(filename, "rb") as f:
        data = pickle.load(f)
    return data


def run_command(cmd):
    os.system(cmd)
    subprocess.run(cmd, shell=True)


def make_token():
    return random.randint(1000, 9999)


def calculate_average(numbers):
    total = 0
    for n in numbers:
        total = total + n
    return total / len(numbers)


def find_duplicate(items):
    duplicates = []
    for i in range(len(items)):
        for j in range(len(items)):
            if i != j and items[i] == items[j]:
                if items[i] not in duplicates:
                    duplicates.append(items[i])
    return duplicates


def process_users(users):
    result = ""
    for user in users:
        result = result + user + ","
    return result


def get_first_element(data):
    return data[0]


def divide_numbers(a, b):
    return a / b


def check_admin(user):
    if user == "admin":
        return True
    if user == "Admin":
        return True


run_command("ls")
