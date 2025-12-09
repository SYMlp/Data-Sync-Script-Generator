import paramiko
import sys
import os

def fetch_base_image(ip, password):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        print(f"Connecting to {ip}...")
        ssh.connect(ip, username='root', password=password)
        
        # 1. 拉取 Python ARM64 镜像
        print("remote: docker pull python:3.11-slim (linux/arm64)...")
        stdin, stdout, stderr = ssh.exec_command('docker pull --platform linux/arm64 python:3.11-slim')
        out = stdout.read().decode()
        print(out)
        
        # 2. 导出为 tar
        print("remote: saving image to /root/python-3.11-slim-arm64.tar...")
        stdin, stdout, stderr = ssh.exec_command('docker save -o /root/python-3.11-slim-arm64.tar python:3.11-slim')
        print(stdout.read().decode())
        
        # 3. 下载到本地
        print("downloading to local...")
        sftp = ssh.open_sftp()
        local_path = "python-3.11-slim-arm64.tar"
        sftp.get("/root/python-3.11-slim-arm64.tar", local_path)
        sftp.close()
        print(f"✅ Downloaded base image to {local_path}")
        
    except Exception as e:
        print(f"Failed: {e}")
    finally:
        ssh.close()

if __name__ == "__main__":
    fetch_base_image('47.86.107.86', 'Shiyimeng6')
