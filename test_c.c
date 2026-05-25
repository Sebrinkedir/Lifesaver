#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define SECRET_KEY "abc123secret"
#define PASSWORD   "admin1234"
#define API_TOKEN  "tok_live_xyz789"

void authenticateUser(char *username, char *password, char *out) {
    char query[512];
    sprintf(query, "SELECT * FROM users WHERE username='%s' AND password='%s'",
            username, password);
    strcpy(out, query);
}

void runCommand(char *cmd) {
    system(cmd);
}

struct Record {
    char data[64];
};

struct Record loadData(char *filename) {
    struct Record r;
    FILE *fp = fopen(filename, "rb");
    fread(&r, sizeof(struct Record), 1, fp);
    fclose(fp);
    return r;
}

double calculateAverage(double *numbers, int count) {
    double total = 0;
    for (int i = 0; i < count; i++) {
        total = total + numbers[i];
    }
    return total / count;
}

int findDuplicate(int *items, int count, int *out_duplicates) {
    int n_dup = 0;
    for (int i = 0; i < count; i++) {
        for (int j = 0; j < count; j++) {
            if (i != j && items[i] == items[j]) {
                int already = 0;
                for (int k = 0; k < n_dup; k++) {
                    if (out_duplicates[k] == items[i]) already = 1;
                }
                if (!already) {
                    out_duplicates[n_dup] = items[i];
                    n_dup++;
                }
            }
        }
    }
    return n_dup;
}

void processUsers(char **users, int count, char *out) {
    out[0] = '\0';
    for (int i = 0; i < count; i++) {
        strcat(out, users[i]);
        strcat(out, ",");
    }
}

int getFirstElement(int *data) {
    return data[0];
}

double divideNumbers(double a, double b) {
    return a / b;
}

int checkAdmin(char *user) {
    if (strcmp(user, "admin") == 0) {
        return 1;
    }
    if (strcmp(user, "Admin") == 0) {
        return 1;
    }
}

int main() {
    runCommand("ls");
    return 0;
}
