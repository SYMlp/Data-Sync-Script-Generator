import paramiko
import sys

def check_status(ip, password):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        print(f"Connecting to {ip}...")
        ssh.connect(ip, username='root', password=password)
        
        commands = [
            "docker ps -a",
            "echo '--- LOGS ---'",
            "docker logs app",
            "echo '--- INSPECT ---'",
            "docker inspect mysql-script-gen:v1 --format '{{.Architecture}} {{.Os}}'"
        ]
        
        for cmd in commands:
            print(f"\n> {cmd}")
            stdin, stdout, stderr = ssh.exec_command(cmd)
            print(stdout.read().decode())
            err = stderr.read().decode()
            if err:
                print(f"ERROR: {err}")
                
    except Exception as e:
        print(f"Connection failed: {e}")
    finally:
        ssh.close()

if __name__ == "__main__":
    check_status('47.86.107.86', 'Shiyimeng6')
