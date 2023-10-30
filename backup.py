import yaml
import subprocess
import os
import sys
from zipfile import ZipFile
import datetime

def cleanup(base_dir, volume_names):
    for volume_name in volume_names:
        volume_dir = f'{base_dir}/{volume_name}_backup'
        if os.path.exists(volume_dir):
            subprocess.run(f"rm -rf {volume_dir}", shell=True)
    zip_file_path = f'{base_dir}/backup.zip'
    if os.path.exists(zip_file_path):
        os.remove(zip_file_path)

def rclone_upload(file_path, remote_name, remote_folder, encrypted_password):
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    encrypted_file = f"{file_path}_{timestamp}_encrypted.zip"
    subprocess.run(f"rclone crypt encode {file_path} {encrypted_file} --password {encrypted_password}", shell=True)
    subprocess.run(f"rclone copy {encrypted_file} {remote_name}:/{remote_folder}/{timestamp}/", shell=True)
    os.remove(encrypted_file)

def main():
    remote_name = os.getenv('RCLONE_REMOTE_NAME')
    remote_folder = os.getenv('RCLONE_REMOTE_FOLDER')
    remote_password = os.getenv('RCLONE_REMOTE_PASSWORD')

    docker_compose_file = sys.argv[1]
    base_dir = os.path.dirname(docker_compose_file)

    # Read the docker-compose file
    with open(docker_compose_file, 'r') as file:
        compose_data = yaml.safe_load(file)

    # Extract volume names
    volume_names = []
    for service, data in compose_data.get('services', {}).items():
        for volume in data.get('volumes', []):
            volume_name = volume.split(':')[0]
            if volume_name not in volume_names:
                volume_names.append(volume_name)

    # Get real volume names
    real_volume_names = []
    for volume_name in volume_names:
        cmd_output = subprocess.getoutput(f'docker volume ls --filter name=^{volume_name}$')
        if cmd_output:
            real_volume_names.append(volume_name)

    # Save the volumes' content as zip
    for real_volume_name in real_volume_names:
        volume_dir = f'{base_dir}/{real_volume_name}_backup'
        os.makedirs(volume_dir, exist_ok=True)
        subprocess.run(f'docker run --rm --volume {real_volume_name}:/backup --volume {volume_dir}:/backup_dir ubuntu tar czf /backup_dir/{real_volume_name}.tar.gz -C / /backup/', shell=True)
        
    # Zip the entire folder
    zip_file_path = f'{base_dir}/backup.zip'
    with ZipFile(zip_file_path, 'w') as zipf:
        for root, dirs, files in os.walk(base_dir):
            for file in files:
                zipf.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), base_dir))

    rclone_upload(zip_file_path, remote_name, remote_folder, remote_password)

    cleanup(base_dir, volume_names)

if __name__ == "__main__":
    main()
