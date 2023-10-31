import os
import sys
import yaml
import subprocess
from zipfile import ZipFile
from socket import gethostname
import requests


def execute_command(command):
    try:
        subprocess.run(
            command, shell=True, check=True, stdout=sys.stdout, stderr=sys.stderr
        )
    except subprocess.CalledProcessError as e:
        sys.stderr.write(f"Error: {e}\n")
        sys.exit(1)


def notify_failure(fail_url):
    try:
        requests.post(fail_url, json={"message": "Backup process failed."})
    except Exception as e:
        sys.stderr.write(f"Failed to notify via URL {fail_url}: {e}\n")


def remove_file_or_dir(path):
    if os.path.exists(path):
        if os.path.isdir(path):
            execute_command(f"rm -rf {path}")
        else:
            os.remove(path)


def cleanup(base_dir, volume_names):
    for volume_name in volume_names:
        remove_file_or_dir(f"{base_dir}/{volume_name}_backup")
    remove_file_or_dir(f"{base_dir}/backup.zip")


def read_docker_compose(file_path):
    try:
        with open(file_path, "r") as file:
            return yaml.safe_load(file)
    except Exception as e:
        sys.stderr.write(f"Failed to read docker-compose file: {e}\n")
        sys.exit(1)


def get_real_volume_names(volume_names):
    real_volume_names = []
    for volume_name in volume_names:
        try:
            cmd_output = subprocess.getoutput(
                f"docker volume ls --filter name=^{volume_name}$"
            )
            if cmd_output:
                real_volume_names.append(volume_name)
        except Exception as e:
            sys.stderr.write(f"Failed to fetch docker volumes: {e}\n")
            sys.exit(1)
    return real_volume_names


def backup_volumes_to_zip(base_dir, real_volume_names):
    zip_file_path = f"{base_dir}/backup.zip"
    with ZipFile(zip_file_path, "w") as zipf:
        for root, dirs, files in os.walk(base_dir):
            for file in files:
                zipf.write(
                    os.path.join(root, file),
                    os.path.relpath(os.path.join(root, file), base_dir),
                )
    return zip_file_path


def rclone_upload(file_path, remote_name, remote_folder, parent_folder_name):
    hostname = get_hostname()
    remote_path = f"{remote_name}:/{remote_folder}/{hostname}/{parent_folder_name}/"
    execute_command(f"rclone copy --progress {file_path} {remote_path}")


def validate_and_notify_env_vars(vars_list):
    fail_url = os.getenv("FAIL_NOTIFY_URL")
    for var in vars_list:
        if not os.getenv(var):
            sys.stderr.write(f"Error: Environment variable {var} is not set.\n")
            if fail_url:
                notify_failure(fail_url)
            sys.exit(1)


def get_hostname() -> str:
    try:
        with open("/etc/host_hostname", "r") as f:
            hostname = f.read().strip()
    except Exception as e:
        hostname = gethostname()
    return hostname


def main():
    validate_and_notify_env_vars(["RCLONE_REMOTE_NAME", "RCLONE_REMOTE_FOLDER"])

    remote_name = os.getenv("RCLONE_REMOTE_NAME")
    remote_folder = os.getenv("RCLONE_REMOTE_FOLDER")
    docker_compose_file = sys.argv[1]
    base_dir = os.path.dirname(docker_compose_file)
    parent_folder_name = os.path.basename(base_dir)

    compose_data = read_docker_compose(docker_compose_file)

    volume_names = []
    for _, data in compose_data.get("services", {}).items():
        for volume in data.get("volumes", []):
            volume_name = volume.split(":")[0]
            if volume_name not in volume_names:
                volume_names.append(volume_name)

    try:
        real_volume_names = get_real_volume_names(volume_names)

        for real_volume_name in real_volume_names:
            volume_dir = f"{base_dir}/{real_volume_name}_backup"
            os.makedirs(volume_dir, exist_ok=True)
            execute_command(
                f"docker run --rm --volume {real_volume_name}:/backup --volume {volume_dir}:/backup_dir ubuntu tar czf /backup_dir/{real_volume_name}.tar.gz -C / /backup/"
            )

        zip_file_path = backup_volumes_to_zip(base_dir, real_volume_names)

        rclone_upload(zip_file_path, remote_name, remote_folder, parent_folder_name)

        cleanup(base_dir, volume_names)
        pass
    except Exception as e:
        sys.stderr.write(f"Backup process failed: {e}\n")
        fail_url = os.getenv("FAIL_NOTIFY_URL")
        if fail_url:
            notify_failure(fail_url)
        sys.exit(1)


if __name__ == "__main__":
    main()
