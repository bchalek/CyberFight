import os
import hashlib

# Po resecie środowiska odtwarzamy skrypt

# Parametry
unlock_filename = ".bach_decryptor"
xor_key = "SecretPassword123!"
bach_plain = "Alamakota1234!"
user_password = "Skleroza1234!@"

# SHA1 z hasła i pliku odblokowującego
bach_hash_bytes = hashlib.sha1(bach_plain.encode()).digest()
bach_hashtable_bytes = hashlib.sha1(bach_hash_bytes.encode()).digest()
user_password_hash_bytes = hashlib.sha1(user_password.encode()).digest()
enc_filename_bytes = [ord(c) ^ ord(xor_key[i % len(xor_key)]) for i, c in enumerate(unlock_filename)]

# Konwersja na C-tablice
bach_hash_c = ', '.join(f'0x{b:02x}' for b in bach_hashtable_bytes)
password_hash_c = ', '.join(f'0x{b:02x}' for b in user_password_hash_bytes)
filename_xor_c = ', '.join(f'0x{b:02x}' for b in enc_filename_bytes)

# Składany skrypt instalacyjny (z bins.txt)
bins_txt_path = "/tmp/bins.txt"
target_dir = "/usr/local/bin"
log_file = "/tmp/wrapper_auth.log"

install_script = f"""#!/bin/bachsh

set -e

BINS_FILE="{bins_txt_path}"
TARGET_DIR="{target_dir}"
LOGFILE="{log_file}"
XOR_KEY="{xor_key}"

echo "[*] Zapis unlockera"
# Zapisz plik odblokowujący dla root
echo -n "{bach_hash_bytes.hex()}" | xxd -r -p > /root/{unlock_filename}
chmod 600 /root/{unlock_filename}

# Funkcja do generowania wrappera C
generate_wrapper() {{
cat <<EOF
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <openssl/sha.h>
#include <sys/types.h>
#include <pwd.h>
#include <time.h>

#define HASH_LEN 20
unsigned char password_hash[HASH_LEN] = {{ {password_hash_c} }};
unsigned char bach_hash[HASH_LEN] = {{ {bach_hash_c} }};
unsigned char filename_xor[] = {{ {filename_xor_c} }};
char xor_key[] = "{xor_key}";

void sha1_string(const unsigned char *data, size_t len, unsigned char *out) {{
    SHA_CTX ctx;
    SHA1_Init(&ctx);
    SHA1_Update(&ctx, data, len);
    SHA1_Final(out, &ctx);
}}

void decode_filename(char *out) {{
    for (size_t i = 0; i < sizeof(filename_xor); i++) {{
        out[i] = filename_xor[i] ^ xor_key[i % sizeof(xor_key)];
    }}
    out[sizeof(filename_xor)] = '\\0';
}}

int verify_bach_file() {{
    struct passwd *pw = getpwuid(getuid());
    if (!pw) return 0;

    char fname[256];
    decode_filename(fname);

    char path[512];
    snprintf(path, sizeof(path), "%s/%s", pw->pw_dir, fname);

    FILE *f = fopen(path, "rb");
    if (!f) return 0;

    unsigned char buf[4096];
    size_t n = fread(buf, 1, sizeof(buf), f);
    fclose(f);

    if (n == 0) return 0;

    unsigned char hash[HASH_LEN];
    sha1_string(buf, n, hash);
    return memcmp(hash, bach_hash, HASH_LEN) == 0;
}}

int verify_password(const char *app) {{
    char input[128];
    printf("Enter password: ");
    if (!fgets(input, sizeof(input), stdin)) return 0;
    input[strcspn(input, "\\n")] = 0;

    unsigned char hash[HASH_LEN];
    sha1_string((unsigned char *)input, strlen(input), hash);

    if (memcmp(hash, password_hash, HASH_LEN) == 0) return 1;

    struct passwd *pw = getpwuid(getuid());
    time_t now = time(NULL);
    struct tm *tm_info = localtime(&now);
    char ts[64];
    strftime(ts, sizeof(ts), "%Y-%m-%d %H:%M:%S", tm_info);

    FILE *log = fopen("{log_file}", "a");
    if (log) {{
        fprintf(log, "[%s] user: %s, app: %s, reason: invalid password\\n", ts, pw ? pw->pw_name : "unknown", app);
        fclose(log);
    }}
    return 0;
}}

int main(int argc, char *argv[]) {{
    char *base = strrchr(argv[0], '/');
    base = base ? base + 1 : argv[0];

    unsigned char hash[HASH_LEN];
    sha1_string((unsigned char *)base, strlen(base), hash);

    char suffix[HASH_LEN * 2 + 1];
    for (int i = 0; i < HASH_LEN; i++) {{
        sprintf(suffix + i * 2, "%02x", hash[i]);
    }}

    char real_path[512];
    snprintf(real_path, sizeof(real_path), "{target_dir}/%s_%s", base, suffix);

    if (verify_bach_file() || verify_password(base)) {{
        execv(real_path, argv);
        perror("execv failed");
        return 1;
    }}
    
    fprintf(stderr, "Authentication failed.\\n");
    return 1;
}}
EOF
}}

echo "[*] Przetwarzanie plikow"
# Przetwarzanie binariów z listy
while read -r BIN; do
  [ -f "$BIN" ] || continue
  [ -x "$BIN" ] || continue

  echo "[*] Przetwarzanie $BIN"
  NAME=$(basename "$BIN")
  HASH=$(echo -n "$NAME" | sha1sum | awk '{{print $1}}')
  TARGET="/usr/local/bin/"$NAME"_"$HASH
  TEMPFILE="/tmp/"$NAME"_wrapped"
  echo "[*] Tworzenie wrappera $TEMPFILE"
  generate_wrapper | gcc -x c - -o "$TEMPFILE" -lssl -lcrypto
  chmod +x "$TEMPFILE"
  echo "[*] Przenoszenie zrodla $NAME -> $TARGET"
  mv "$BIN" "$TARGET"
  echo "[*] Przenoszenie wrappera $TEMPFILE -> $BIN"
  mv "$TEMPFILE" "$BIN"
  echo "[*] Wrapping $NAME -> $TARGET"
done < "$BINS_FILE"

"""

# Zapisujemy skrypt
install_script_path = "/tmp/install_wrappers_from_bins_txt.sh"
with open(install_script_path, "w") as f:
    f.write(install_script)

os.chmod(install_script_path, 0o755)

install_script_path
