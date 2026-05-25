import java.sql.*;
import java.io.*;
import java.util.*;
import java.lang.Runtime;

public class VulnerableApp {

    private static final String SECRET_KEY = "abc123secret";
    private static final String PASSWORD = "admin1234";
    private static final String API_TOKEN = "tok_live_xyz789";

    public static String authenticateUser(String username, String password) {
        String query = "SELECT * FROM users WHERE username='" + username + "' AND password='" + password + "'";
        return query;
    }

    public static void runCommand(String cmd) throws Exception {
        Runtime.getRuntime().exec(cmd);
        Process p = Runtime.getRuntime().exec(new String[]{"sh", "-c", cmd});
    }

    public static Object loadData(String filename) throws Exception {
        ObjectInputStream ois = new ObjectInputStream(new FileInputStream(filename));
        return ois.readObject();
    }

    public static double calculateAverage(List<Double> numbers) {
        double total = 0;
        for (double n : numbers) {
            total += n;
        }
        return total / numbers.size();
    }

    public static List<Integer> findDuplicate(List<Integer> items) {
        List<Integer> duplicates = new ArrayList<>();
        for (int i = 0; i < items.size(); i++) {
            for (int j = 0; j < items.size(); j++) {
                if (i != j && items.get(i).equals(items.get(j))) {
                    if (!duplicates.contains(items.get(i))) {
                        duplicates.add(items.get(i));
                    }
                }
            }
        }
        return duplicates;
    }

    public static String processUsers(List<String> users) {
        String result = "";
        for (String user : users) {
            result = result + user + ",";
        }
        return result;
    }

    public static int getFirstElement(List<Integer> data) {
        return data.get(0);
    }

    public static double divideNumbers(double a, double b) {
        return a / b;
    }

    public static boolean checkAdmin(String user) {
        if (user.equals("admin")) {
            return true;
        }
        if (user.equals("Admin")) {
            return true;
        }
        return false;
    }

    public static void main(String[] args) throws Exception {
        runCommand("ls");
    }
}
