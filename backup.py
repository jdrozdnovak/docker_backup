import os
import sys
import yaml
import subprocess
import logging
from zipfile import ZipFile
import requests
from datetime import datetime
import socket

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)


class DockerBackup:
    """Class for performing Docker backups."""

    def __init__(self):
        self.remote_folder = None
        self.remote_name = None
        self.fail_notify_url = None
        self.read_env_vars_from_file("/env_var")

    @staticmethod
    def normalize_path(path):
        """Normalize a filesystem path."""
        return os.path.normpath(os.path.abspath(path))

    def read_env_vars_from_file(self, file_path):
        try:
            with open(file_path, "r") as f:
                lines = f.readlines()
            for line in lines:
                key, value = line.strip().split("=", 1)
                if key == "RCLONE_REMOTE_FOLDER":
                    self.remote_folder = value
                elif key == "RCLONE_REMOTE_NAME":
                    self.remote_name = value
                elif key == "FAIL_NOTIFY_URL":
                    self.fail_notify_url = value
            self.validate_and_notify_env_vars()
        except Exception as e:
            sys.stderr.write(f"Error reading environment variables from file: {e}\n")
            self.notify_failure()
            sys.exit(1)

    def execute_command(self, command):
        try:
            logger.info(f"Running\n{command}")
            result = subprocess.run(
                command, shell=True, check=True, capture_output=True, text=True
            )
            logger.info(result)
            return result
        except subprocess.CalledProcessError as exc:
            self.notify_failure()
            logger.error(f"Error: {exc}")
            sys.exit(1)

    def notify_failure(self):
        """Notify failure through a URL."""
        try:
            requests.get(
                self.fail_notify_url,
            )
        except Exception as exc:
            logger.error(f"Failed to notify via URL {self.fail_notify_url}: {exc}")

    def validate_and_notify_env_vars(self):
        """Validate and notify for environment variables."""
        for var in [self.remote_name, self.remote_folder]:
            if not var:
                self.notify_failure()
                logger.error("Required environment variable is not set.")
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
            logger.error(f"Failed to read docker-compose file: {e}")
            sys.exit(1)

    def list_docker_volumes(self):
        command = 'docker volume ls --format "{{.Name}}"'
        try:
            result = self.execute_command(command)
            volumes = result.stdout.strip().split("\n")
            logger.info(volumes)
            return volumes
        except subprocess.CalledProcessError as e:
            logger.error("Failed to list Docker volumes: %s", e)
            return []

    def get_real_volume_names(self, compose_data, base_dir, docker_volumes):
        real_volume_names = []
        for service_name, data in compose_data.get("services", {}).items():
            if service_name == "docker-backup":
                continue
            for volume in data.get("volumes", []):
                volume_name = volume.split(":")[0]
                if "/" not in volume_name:
                    volume_found = False
                    for docker_volume_name in docker_volumes:
                        if volume_name in docker_volume_name:
                            volume_name = docker_volume_name
                            volume_found = True
                            break
                    if not volume_found:
                        continue
                elif volume_name.startswith(".") or not volume_name.endswith("/"):
                    logger.info(f"skipping : {volume_name}")
                    continue
                elif os.path.isabs(volume_name):
                    volume_name = self.normalize_path(
                        os.path.join(base_dir, volume_name)
                    )
                if volume_name not in real_volume_names:
                    real_volume_names.append(volume_name)
        return real_volume_names

    def backup_volumes_to_zip(self, base_dir, real_volume_names):
        zip_file_path = f"{base_dir}/backup.zip"
        with ZipFile(zip_file_path, "w") as zipf:
            for root, _, files in os.walk(base_dir):
                for file in files:
                    full_path = os.path.join(root, file)
                    if full_path == zip_file_path:
                        continue
                    zipf.write(full_path, os.path.relpath(full_path, base_dir))
        return zip_file_path

    def rclone_upload(self, file_path, parent_folder_name, suffix):
        hostname = self.get_hostname()
        remote_path = (
            f"{self.remote_name}:/{self.remote_folder}/{hostname}/{parent_folder_name}/"
        )
        remote_old_path = f"{self.remote_name}:/{self.remote_folder}/old/{hostname}/{parent_folder_name}/"
        self.execute_command(
            f"rclone sync {file_path} {remote_path} --backup-dir {remote_old_path} --suffix {suffix} --suffix-keep-extension --cache-dir /tmp/"
        )

    def get_hostname(self) -> str:
        """Retrieve the hostname."""
        try:
            with open("/etc/host_hostname", "r") as file:
                hostname = file.read().strip()
        except FileNotFoundError:
            hostname = socket.gethostname()
        return hostname

    def main(self, docker_compose_file):
        docker_volumes = self.list_docker_volumes()
        base_dir = os.path.dirname(docker_compose_file)
        compose_data = self.read_docker_compose(docker_compose_file)
        real_volume_names = self.get_real_volume_names(compose_data, base_dir, docker_volumes)

        for real_volume_name in real_volume_names:
            if real_volume_name.startswith("/"):
                volume_backup_path = f"/backup_dir{real_volume_name}.tar.gz"
            else:
                volume_backup_path = f"/backup_dir/{real_volume_name}.tar.gz"
            self.execute_command(
                f"docker run --rm --volume {real_volume_name}:/backup --volume {base_dir}:/backup_dir ubuntu tar czfP {volume_backup_path} -C / /backup/"
            )

        backup_zip_path = self.backup_volumes_to_zip(base_dir, real_volume_names)
        self.rclone_upload(
            backup_zip_path,
            os.path.basename(base_dir),
            datetime.now().strftime("%Y%m%d%H%M%S"),
        )
        self.cleanup(base_dir, real_volume_names)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.stderr.write("Usage: backup.py <path_to_docker_compose_file>\n")
        sys.exit(1)

    docker_compose_file = sys.argv[1]
    backup = DockerBackup()
    backup.main(docker_compose_file)
