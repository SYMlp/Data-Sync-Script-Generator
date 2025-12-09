import paramiko

def check_ssh(ip, password):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        print(f"Connecting to {ip}...")
        client.connect(ip, username='root', password=password)
        stdin, stdout, stderr = client.exec_command('whoami && git --version && docker --version')
        print(f"✅ Connection successful!\nOutput:\n{stdout.read().decode()}")
        return True
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False
    finally:
        client.close()

if __name__ == "__main__":
    check_ssh('47.86.107.86', 'Shiyimeng6')
