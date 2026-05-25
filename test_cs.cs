using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.Serialization.Formatters.Binary;

namespace VulnerableApp
{
    public class Program
    {
        private const string SECRET_KEY = "abc123secret";
        private const string PASSWORD = "admin1234";
        private const string API_TOKEN = "tok_live_xyz789";

        public static string AuthenticateUser(string username, string password)
        {
            string query = "SELECT * FROM users WHERE username='" + username + "' AND password='" + password + "'";
            return query;
        }

        public static void RunCommand(string cmd)
        {
            System.Diagnostics.Process.Start("cmd.exe", "/c " + cmd);
        }

        public static object LoadData(string filename)
        {
            BinaryFormatter formatter = new BinaryFormatter();
            FileStream fs = new FileStream(filename, FileMode.Open);
            return formatter.Deserialize(fs);
        }

        public static double CalculateAverage(List<double> numbers)
        {
            double total = 0;
            foreach (double n in numbers)
            {
                total = total + n;
            }
            return total / numbers.Count;
        }

        public static List<int> FindDuplicate(List<int> items)
        {
            List<int> duplicates = new List<int>();
            for (int i = 0; i < items.Count; i++)
            {
                for (int j = 0; j < items.Count; j++)
                {
                    if (i != j && items[i] == items[j])
                    {
                        if (!duplicates.Contains(items[i]))
                        {
                            duplicates.Add(items[i]);
                        }
                    }
                }
            }
            return duplicates;
        }

        public static string ProcessUsers(List<string> users)
        {
            string result = "";
            foreach (string user in users)
            {
                result = result + user + ",";
            }
            return result;
        }

        public static int GetFirstElement(List<int> data)
        {
            return data[0];
        }

        public static double DivideNumbers(double a, double b)
        {
            return a / b;
        }

        public static bool CheckAdmin(string user)
        {
            if (user == "admin")
            {
                return true;
            }
            if (user == "Admin")
            {
                return true;
            }
        }

        public static void Main(string[] args)
        {
            RunCommand("ls");
        }
    }
}
