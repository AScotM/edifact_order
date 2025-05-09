import hashlib
import os

def hash_file(filepath):
    h = hashlib.blake2b()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):  # 64 KB buffer
            h.update(chunk)
    return h.hexdigest()

def main():
    for fname in os.listdir("."):
        if os.path.isfile(fname):
            checksum = hash_file(fname)
            print(f"{checksum}  {fname}")

if __name__ == "__main__":
    main()
