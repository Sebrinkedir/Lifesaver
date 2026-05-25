require 'json'

SECRET_KEY = "abc123secret"
PASSWORD = "admin1234"
API_TOKEN = "tok_live_xyz789"

def authenticate_user(username, password)
  query = "SELECT * FROM users WHERE username='" + username + "' AND password='" + password + "'"
  return query
end

def run_command(cmd)
  system(cmd)
  `#{cmd}`
end

def load_data(filename)
  data = Marshal.load(File.read(filename))
  return data
end

def calculate_average(numbers)
  total = 0
  numbers.each do |n|
    total = total + n
  end
  return total / numbers.length
end

def find_duplicate(items)
  duplicates = []
  for i in 0...items.length
    for j in 0...items.length
      if i != j && items[i] == items[j]
        if !duplicates.include?(items[i])
          duplicates.push(items[i])
        end
      end
    end
  end
  return duplicates
end

def process_users(users)
  result = ""
  users.each do |user|
    result = result + user + ","
  end
  return result
end

def get_first_element(data)
  return data[0]
end

def divide_numbers(a, b)
  return a / b
end

def check_admin(user)
  if user == "admin"
    return true
  end
  if user == "Admin"
    return true
  end
end

puts run_command("ls")
