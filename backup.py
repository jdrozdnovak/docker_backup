import os
import sys
import yaml
import subprocess
from zipfile import ZipFile
from socket import gethostname
import requests
from datetime import datetime


class DockerBackup:
    def __init__(self):
        self.remote_name = os.getenv("RCLONE_REMOTE_NAME")
        self.remote_folder = os.getenv("RCLONE_REMOTE_FOLDER")
        self.fail_notify_url = os.getenv("FAIL_NOTIFY_URL")
        self.validate_and_notify_env_vars()

    def execute_command(self, command):
        try:
            subprocess.run(
                command, shell=True, check=True, stdout=sys.stdout, stderr=sys.stderr
            )
        except subprocess.CalledProcessError as e:
            self.notify_failure()
            sys.stderr.write(f"Error: {e}\n")
            sys.exit(1)

    def notify_failure(self):
        if self.fail_notify_url:
            try:
                requests.post(
                    self.fail_notify_url, json={"message": "Backup process failed."}
                )
            except Exception as e:
                sys.stderr.write(
                    f"Failed to notify via URL {self.fail_notify_url}: {e}\n"
                )

    def validate_and_notify_env_vars(self):
        for var in [self.remote_name, self.remote_folder]:
            if not var:
                self.notify_failure()
                sys.stderr.write(f"Error: Required environment variable is not set.\n")
                sys.exit(1)

    def remove_file_or_dir(self, path):
        if os.path.exists(path):
            if os.path.isdir(path):
                self.execute_command(f"rm -rf {path}")
            else:
                os.remove(path)

    def cleanup(self, base_dir, volume_names):
        for volume_name in volume_names:
            self.remove_file_or_dir(f"{base_dir}/{volume_name}_backup")
        self.remove_file_or_dir(f"{base_dir}/backup.zip")

    def read_docker_compose(self, file_path):
        try:
            with open(file_path, "r") as file:
                return yaml.safe_load(file)
        except Exception as e:
            self.notify_failure()
            sys.stderr.write(f"Failed to read docker-compose file: {e}\n")
            sys.exit(1)

    def get_real_volume_names(self, volume_names):
        real_volume_names = []
        for volume_name in volume_names:
            try:
                cmd_output = subprocess.getoutput(
                    f"docker volume ls --filter name=^{volume_name}$"
                )
                if cmd_output:
                    real_volume_names.append(volume_name)
            except Exception as e:
                self.notify_failure()
                sys.stderr.write(f"Failed to fetch docker volumes: {e}\n")
                sys.exit(1)
        return real_volume_names

    def backup_volumes_to_zip(self, base_dir, real_volume_names):
        zip_file_path = f"{base_dir}/backup.zip"
        with ZipFile(zip_file_path, "w") as zipf:
            for root, dirs, files in os.walk(base_dir):
                for file in files:
                    zipf.write(
                        os.path.join(root, file),
                        os.path.relpath(os.path.join(root, file), base_dir),
                    )
        return zip_file_path

    def rclone_upload(self, file_path, parent_folder_name, suffix):
        hostname = get_hostname()
        remote_path = (
            f"{self.remote_name}:/{self.remote_folder}/{hostname}/{parent_folder_name}/"
        )
        remote_old_path = (
            f"{self.remote_name}:/{self.remote_folder}/old/{hostname}/{parent_folder_name}/"
        )
        self.execute_command(f"rclone sync --progress {file_path} {remote_path} --backup-dir {remote_old_path} --suffix {suffix} --suffix-keep-extension")

    def main(self, docker_compose_file):
        try:
            suffix = datetime.now().strftime("%y%m%d%H%M")
            base_dir = os.path.dirname(docker_compose_file)
            parent_folder_name = os.path.basename(base_dir)

            compose_data = self.read_docker_compose(docker_compose_file)

            volume_names = []
            for service_name, data in compose_data.get("services", {}).items():
                if service_name == "docker-backup":
                    continue
                for volume in data.get("volumes", []):
                    volume_name = volume.split(":")[0]
                    if volume_name not in volume_names:
                        volume_names.append(volume_name)

            real_volume_names = self.get_real_volume_names(volume_names)

            for real_volume_name in real_volume_names:
                volume_dir = f"{base_dir}/{real_volume_name}_backup"
                os.makedirs(volume_dir, exist_ok=True)
                self.execute_command(
                    f"docker run --rm --volume {real_volume_name}:/backup --volume {volume_dir}:/backup_dir ubuntu tar czf /backup_dir/{real_volume_name}.tar.gz -C / /backup/"
                )

            zip_file_path = self.backup_volumes_to_zip(base_dir, real_volume_names)

            self.rclone_upload(zip_file_path, parent_folder_name, suffix)

            self.cleanup(base_dir, volume_names)
        except Exception as e:
            sys.stderr.write(f"Backup process failed: {e}\n")
            self.notify_failure()
            sys.exit(1)


def get_hostname() -> str:
    try:
        with open("/etc/host_hostname", "r") as f:
            hostname = f.read().strip()
    except Exception:
        hostname = gethostname()
    return hostname


if __name__ == "__main__":
    docker_compose_file = sys.argv[1]
    backup = DockerBackup()
    backup.main(docker_compose_file)
