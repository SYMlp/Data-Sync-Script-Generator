import os
import time
import json
import argparse
import paramiko
import sys
from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.acs_exception.exceptions import ClientException
from aliyunsdkecs.request.v20140526.RunInstancesRequest import RunInstancesRequest
from aliyunsdkecs.request.v20140526.DescribeInstancesRequest import DescribeInstancesRequest
from aliyunsdkecs.request.v20140526.DeleteInstanceRequest import DeleteInstanceRequest
from aliyunsdkecs.request.v20140526.AllocatePublicIpAddressRequest import AllocatePublicIpAddressRequest
from aliyunsdkecs.request.v20140526.DescribeImagesRequest import DescribeImagesRequest
from aliyunsdkecs.request.v20140526.CreateSecurityGroupRequest import CreateSecurityGroupRequest
from aliyunsdkecs.request.v20140526.AuthorizeSecurityGroupRequest import AuthorizeSecurityGroupRequest
from aliyunsdkecs.request.v20140526.DescribeSecurityGroupsRequest import DescribeSecurityGroupsRequest
from aliyunsdkvpc.request.v20160428.DescribeVpcsRequest import DescribeVpcsRequest
from aliyunsdkvpc.request.v20160428.CreateVpcRequest import CreateVpcRequest
from aliyunsdkvpc.request.v20160428.DescribeVSwitchesRequest import DescribeVSwitchesRequest
from aliyunsdkvpc.request.v20160428.CreateVSwitchRequest import CreateVSwitchRequest

# 配置
REGION_ID = "cn-hangzhou" # 默认杭州，因为这里通常有倚天710实例
INSTANCE_TYPE = "ecs.c8y.large" # ARM 架构实例 (倚天710)
# 使用公共镜像别名，而不是具体的 ImageId，或者让阿里云自动选择最新的 Ubuntu ARM64
# 注意：阿里云 API 对镜像 ID 校验很严。
# 既然 ImageId 总是变，我们增加一个 helper 函数来动态获取最新的 ARM Ubuntu 镜像
IMAGE_ID = "" # 将在 runtime 动态获取
ZONE_ID = "cn-hangzhou-k" # 需要支持 ARM 的可用区

# 获取环境变量
ACCESS_KEY_ID = os.environ.get("ALIYUN_ACCESS_KEY_ID")
ACCESS_KEY_SECRET = os.environ.get("ALIYUN_ACCESS_KEY_SECRET")

if not ACCESS_KEY_ID or not ACCESS_KEY_SECRET:
    print("❌ 错误: 未找到阿里云 AccessKey 环境变量。")
    print("请设置 ALIYUN_ACCESS_KEY_ID 和 ALIYUN_ACCESS_KEY_SECRET")
    sys.exit(1)

client = AcsClient(ACCESS_KEY_ID, ACCESS_KEY_SECRET, REGION_ID)

def prepare_network():
    print("🌐 正在准备网络环境...")
    
    # 1. 获取或创建 VPC
    vpc_id = None
    try:
        req = DescribeVpcsRequest()
        req.set_VpcName("Verification-VPC")
        resp = json.loads(client.do_action_with_exception(req))
        if resp['Vpcs']['Vpc']:
            vpc_id = resp['Vpcs']['Vpc'][0]['VpcId']
            print(f"✅ 复用现有专用 VPC: {vpc_id}")
        else:
            print("creating vpc...")
            req = CreateVpcRequest()
            req.set_VpcName("Verification-VPC")
            req.set_CidrBlock("192.168.0.0/16")
            resp = json.loads(client.do_action_with_exception(req))
            vpc_id = resp['VpcId']
            print(f"✅ 创建新专用 VPC: {vpc_id}")
            # 等待 VPC 可用
            time.sleep(10)
    except Exception as e:
        print(f"❌ 网络初始化失败 (VPC): {e}")
        sys.exit(1)

    # 2. 获取或创建 VSwitch (在目标 Zone)
    vswitch_id = None
    try:
        req = DescribeVSwitchesRequest()
        req.set_VpcId(vpc_id)
        req.set_ZoneId(ZONE_ID)
        resp = json.loads(client.do_action_with_exception(req))
        if resp['VSwitches']['VSwitch']:
            vswitch_id = resp['VSwitches']['VSwitch'][0]['VSwitchId']
            print(f"✅ 复用现有 VSwitch: {vswitch_id}")
        else:
            print(f"creating vswitch in {ZONE_ID}...")
            req = CreateVSwitchRequest()
            req.set_VpcId(vpc_id)
            req.set_ZoneId(ZONE_ID)
            req.set_CidrBlock("192.168.1.0/24")
            req.set_VSwitchName("Verification-VSwitch-ARM")
            resp = json.loads(client.do_action_with_exception(req))
            vswitch_id = resp['VSwitchId']
            print(f"✅ 创建新 VSwitch: {vswitch_id}")
            time.sleep(5)
    except Exception as e:
        print(f"❌ 网络初始化失败 (VSwitch): {e}")
        sys.exit(1)

    # 3. 获取 or 创建 Security Group
    sg_id = None
    try:
        req = DescribeSecurityGroupsRequest()
        req.set_VpcId(vpc_id)
        req.set_SecurityGroupName("Verification-SG")
        resp = json.loads(client.do_action_with_exception(req))
        if resp['SecurityGroups']['SecurityGroup']:
            sg_id = resp['SecurityGroups']['SecurityGroup'][0]['SecurityGroupId']
            print(f"✅ 复用现有安全组: {sg_id}")
        else:
            print("creating security group...")
            req = CreateSecurityGroupRequest()
            req.set_VpcId(vpc_id)
            req.set_SecurityGroupName("Verification-SG")
            req.set_Description("Auto created for ARM verification")
            resp = json.loads(client.do_action_with_exception(req))
            sg_id = resp['SecurityGroupId']
            print(f"✅ 创建新安全组: {sg_id}")
            
            # 授权端口 22 和 8501
            for port in ["22", "8501"]:
                req = AuthorizeSecurityGroupRequest()
                req.set_SecurityGroupId(sg_id)
                req.set_IpProtocol("tcp")
                req.set_PortRange(f"{port}/{port}")
                req.set_SourceCidrIp("0.0.0.0/0")
                client.do_action_with_exception(req)
            print("✅ 已开放端口 22, 8501")

    except Exception as e:
        print(f"❌ 网络初始化失败 (SecurityGroup): {e}")
        sys.exit(1)
        
    return vswitch_id, sg_id

def get_latest_arm_image():
    print("🔍 正在查找最新的 Ubuntu ARM64 镜像...")
    request = DescribeImagesRequest()
    request.set_ImageOwnerAlias("system")
    request.set_Architecture("arm64")
    request.set_PageSize(50)
    # 模糊匹配 Ubuntu
    request.set_ImageName("ubuntu_22_04_arm64*") 
    
    try:
        response = client.do_action_with_exception(request)
        images = json.loads(response)['Images']['Image']
        # 按创建时间倒序排序
        images.sort(key=lambda x: x['CreationTime'], reverse=True)
        if images:
            latest_image = images[0]
            print(f"✅ 找到最新镜像: {latest_image['ImageId']} ({latest_image['OSName']})")
            return latest_image['ImageId']
        else:
            print("❌ 未找到 Ubuntu ARM64 镜像")
            sys.exit(1)
    except ClientException as e:
        print(f"❌ 获取镜像列表失败: {e}")
        sys.exit(1)

def get_instance_status(instance_id):
    request = DescribeInstancesRequest()
    request.set_InstanceIds(json.dumps([instance_id]))
    response = client.do_action_with_exception(request)
    data = json.loads(response)
    if data['Instances']['Instance']:
        return data['Instances']['Instance'][0]['Status']
    return None

def get_instance_ip(instance_id):
    request = DescribeInstancesRequest()
    request.set_InstanceIds(json.dumps([instance_id]))
    response = client.do_action_with_exception(request)
    data = json.loads(response)
    if data['Instances']['Instance']:
        public_ips = data['Instances']['Instance'][0]['PublicIpAddress']['IpAddress']
        if public_ips:
            return public_ips[0]
    return None

def create_instance():
    # 0. 准备网络资源
    vswitch_id, sg_id = prepare_network()

    # 动态获取镜像 ID
    image_id = get_latest_arm_image()

    print(f"🚀 正在创建 ARM 实例 ({INSTANCE_TYPE})...")
    request = RunInstancesRequest()
    request.set_ImageId(image_id)

    request.set_InstanceType(INSTANCE_TYPE)
    request.set_InstanceName("Verification-Worker-ARM64")
    request.set_InternetChargeType("PayByTraffic") # 按流量计费
    request.set_InternetMaxBandwidthOut(100) # 100M 带宽，加快上传
    request.set_Password("Test@123456") # 临时密码
    request.set_Amount(1)
    
    request.set_SystemDiskCategory("cloud_essd") # 显式指定 ESSD
    request.set_SystemDiskSize(40) 

    # 使用自动准备的网络资源
    request.set_SecurityGroupId(sg_id)
    request.set_VSwitchId(vswitch_id)

    try:
        response = client.do_action_with_exception(request)

        instance_id = json.loads(response)['InstanceIdUpdates']['InstanceIdUpdate'][0]['InstanceId']
        print(f"✅ 实例已创建: {instance_id}")
        return instance_id
    except ClientException as e:
        print(f"❌ 创建实例失败: {e}")
        sys.exit(1)

def wait_for_running(instance_id):
    print("⏳ 等待实例启动...")
    while True:
        status = get_instance_status(instance_id)
        if status == "Running":
            print("✅ 实例已运行")
            break
        time.sleep(5)
    
    # 等待 IP 分配和 SSH 服务准备好
    time.sleep(20) 
    return get_instance_ip(instance_id)

def run_remote_commands(ip, tar_path, password):
    print(f"🔗 连接到 {ip}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(ip, username='root', password=password)
        
        # 1. 安装 Docker (兼容 CentOS 7)
        print("🛠️  正在检查/安装 Docker...")
        # 先检查是否已安装
        stdin, stdout, stderr = ssh.exec_command('docker -v')
        if stdout.channel.recv_exit_status() != 0:
             print("   Docker 未安装，开始安装...")
             # CentOS 7 安装 Docker 需要特定步骤
             install_cmd = (
                 "yum install -y yum-utils && "
                 "yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo && "
                 "yum install -y docker-ce docker-ce-cli containerd.io && "
                 "systemctl start docker && "
                 "systemctl enable docker"
             )
             stdin, stdout, stderr = ssh.exec_command(install_cmd)
             exit_status = stdout.channel.recv_exit_status()
             if exit_status != 0:
                 print(f"❌ Docker 安装失败: {stderr.read().decode()}")
                 return False
        else:
             print("   Docker 已安装，跳过。")

        # 2. 上传 tar 包
        print(f"📤 正在上传镜像包: {tar_path}...")
        sftp = ssh.open_sftp()
        remote_path = f"/root/{os.path.basename(tar_path)}"
        sftp.put(tar_path, remote_path)
        sftp.close()

        # 3. 加载镜像
        print("📦 正在加载镜像...")
        stdin, stdout, stderr = ssh.exec_command(f'docker load -i {remote_path}')
        exit_status = stdout.channel.recv_exit_status()
        if exit_status != 0:
            print(f"❌ 镜像加载失败: {stderr.read().decode()}")
            return False
            
        # 4. 运行容器 (先清理旧容器)
        print("🏃 正在启动容器...")
        ssh.exec_command('docker rm -f app') # 强制删除旧容器
        
        stdin, stdout, stderr = ssh.exec_command('docker run -d -p 8501:8501 --name app mysql-script-gen:v1')
        exit_status = stdout.channel.recv_exit_status()
        if exit_status != 0:
            print(f"❌ 容器启动失败: {stderr.read().decode()}")
            return False

        # 5. 验证服务
        print("🔍 正在验证服务健康状态...")
        time.sleep(10) # 等待服务启动
        stdin, stdout, stderr = ssh.exec_command('curl -v http://localhost:8501')
        exit_status = stdout.channel.recv_exit_status()
        output = stdout.read().decode()
        
        if "Streamlit" in output or exit_status == 0:
            print("✅ 验证成功！服务响应正常。")
            return True
        else:
            print("❌ 验证失败：无法访问服务。")
            print(output)
            return False

    except Exception as e:
        print(f"❌ SSH 连接或执行出错: {e}")
        return False
    finally:
        ssh.close()


def delete_instance(instance_id):
    print(f"🗑️  正在释放实例 {instance_id}...")
    request = DeleteInstanceRequest()
    request.set_InstanceId(instance_id)
    request.set_Force(True) # 强制释放运行中的实例
    try:
        client.do_action_with_exception(request)
        print("✅ 实例已释放")
    except ClientException as e:
        print(f"⚠️ 释放实例失败，请手动检查: {e}")

def main():
    parser = argparse.ArgumentParser(description="在阿里云 ARM 实例上验证 Docker 镜像")
    parser.add_argument("tar_path", help="Docker 镜像 tar 包路径")
    parser.add_argument("--keep", action="store_true", help="验证失败后保留实例以便调试")
    parser.add_argument("--existing-ip", help="使用现有的实例 IP 进行验证，跳过创建步骤")
    parser.add_argument("--password", help="SSH 密码 (仅在使用 existing-ip 时需要)", default="Shiyimeng6")
    args = parser.parse_args()

    if not os.path.exists(args.tar_path):
        print(f"❌ 文件不存在: {args.tar_path}")
        sys.exit(1)

    instance_id = None
    ip = None
    
    # 模式 A: 使用现有实例
    if args.existing_ip:
        print(f"🚀 使用现有实例: {args.existing_ip}")
        ip = args.existing_ip
        # 在这种模式下，不涉及实例的创建与销毁
        run_remote_commands(ip, args.tar_path, args.password)
        return

    # 模式 B: 自动创建实例
    instance_id = create_instance()
    success = False
    
    try:
        ip = wait_for_running(instance_id)
        if ip:
            success = run_remote_commands(ip, args.tar_path, "Test@123456")
    finally:
        if args.keep:
             print(f"⚠️  调试模式: 实例 {instance_id} ({ip}) 未释放，请手动登录调试。")
             print("完成后请务必手动释放实例！")
        elif success:
            delete_instance(instance_id)
        else:
            # 失败时，默认改为不释放，方便排查，除非明确要求强制清理（这里逻辑可以灵活调整）
            # 根据用户最新指示：先开着调试
            print(f"❌ 验证失败。实例 {instance_id} ({ip}) 已保留以便调试。")
            print("请使用 SSH 登录排查问题，完成后请手动释放！")

if __name__ == "__main__":
    main()
