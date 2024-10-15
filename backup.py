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
        self.remote_folder: str = None
        self.remote_name: str = None
        self.fail_notify_url: str = None
        self.backup_successful: bool = True
        self.debug_mode: bool = os.getenv("DEBUG", "false").lower() == "true"
        self.read_env_vars_from_file("/env_var")

        if self.debug_mode:
            logger.setLevel(logging.DEBUG)
            logger.debug("Debug mode enabled")

    @staticmethod
    def normalize_path(path: str) -> str:
        """Normalize a filesystem path."""
        return os.path.normpath(os.path.abspath(path))

    def read_env_vars_from_file(self, file_path: str):
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
        except Exception as e:
            logger.error(f"Error reading environment variables from file: {e}")
            self.backup_successful = False

    def execute_command(self, command: str) -> subprocess.CompletedProcess:
        logger.info(f"Executing command: {command}")
        try:
            result = subprocess.run(
                command, shell=True, check=True, capture_output=True, text=True
            )
            logger.info("Command executed successfully.")
            return result
        except subprocess.CalledProcessError as exc:
            self.backup_successful = False
            logger.error(f"Command execution failed with error: {exc}")
            return None

    def remove_file_or_dir(self, path: str):
        """Remove a file or directory without using shutil, with error handling."""
        try:
            if os.path.exists(path):
                if os.path.isfile(path):
                    os.remove(path)
                    logger.info(f"Removed file: {path}")
                elif os.path.isdir(path):
                    # Recursively delete directory contents
                    for root, dirs, files in os.walk(path, topdown=False):
                        for name in files:
                            os.remove(os.path.join(root, name))
                        for name in dirs:
                            os.rmdir(os.path.join(root, name))
                    # Remove the directory itself
                    os.rmdir(path)
                    logger.info(f"Removed directory and its contents: {path}")
                else:
                    logger.warning(
                        f"Path is neither a file nor a directory: {path}"
                    )
            else:
                logger.warning(f"Path does not exist: {path}")
        except Exception as e:
            logger.error(f"Failed to remove {path}: {e}")

    def notify_failure(self):
        """Notify failure through a URL."""
        if not self.backup_successful and self.fail_notify_url:
            try:
                requests.get(self.fail_notify_url)
                logger.info("Failure notification sent.")
            except Exception as exc:
                logger.error(
                    f"Failed to notify via URL {self.fail_notify_url}: {exc}"
                )

    def cleanup(self, base_dir: str, volume_names: list):
        """Cleanup backup files and directories."""
        for volume_name in volume_names:
            backup_path = f"{base_dir}/{volume_name}_backup"
            if os.path.exists(backup_path):
                self.remove_file_or_dir(backup_path)
        zip_path = f"{base_dir}/backup.zip"
        if os.path.exists(zip_path):
            self.remove_file_or_dir(zip_path)

    def read_docker_compose(self, file_path: str) -> dict:
        try:
            with open(file_path, "r") as file:
                return yaml.safe_load(file)
        except Exception as e:
            logger.error(f"Failed to read docker-compose file: {e}")
            self.backup_successful = False
            return {}

    def list_docker_volumes(self) -> list:
        command = 'docker volume ls --format "{{.Name}}"'
        result = self.execute_command(command)
        if result:
            volumes = result.stdout.strip().split("\n")
            return volumes
        else:
            return []

    def backup_volumes_to_zip(self, base_dir, real_volume_names):
        logger.info("Starting backup of volumes to zip file...")
        zip_file_path = f"{base_dir}/backup.zip"
        with ZipFile(zip_file_path, 'w') as zipf:
            for volume_name in real_volume_names:
                logger.info(f"Backing up volume: {volume_name}")
                volume_path = os.path.join(base_dir, volume_name) if not volume_name.startswith("/") else volume_name
                for root, _, files in os.walk(volume_path):
                    for file in files:
                        full_path = os.path.join(root, file)
                        relative_path = os.path.relpath(full_path, base_dir if volume_path.startswith(base_dir) else volume_path)
                        zipf.write(full_path, relative_path)
        logger.info(f"Backup completed successfully. Zip file created at: {zip_file_path}")
        return zip_file_path


    def rclone_upload(self, file_path, parent_folder_name, suffix):
        hostname = self.get_hostname()
        remote_path = f"{self.remote_name}:/{self.remote_folder}/{hostname}/{parent_folder_name}/"
        remote_old_path = f"{self.remote_name}:/{self.remote_folder}/old/{hostname}/{parent_folder_name}/"
        rclone_flags = "-vv" if self.debug_mode else ""
        self.execute_command(
            f"rclone sync {file_path} {remote_path} --backup-dir {remote_old_path} {rclone_flags} --suffix {suffix} --suffix-keep-extension --cache-dir /tmp/"
        )

    def get_hostname(self) -> str:
        """Retrieve the hostname."""
        try:
            with open("/etc/host_hostname", "r") as file:
                hostname = file.read().strip()
        except FileNotFoundError:
            hostname = socket.gethostname()
        return hostname

    def main(self, docker_compose_file: str):
        try:
            logger.info(f"Starting backup process for Docker compose file: {docker_compose_file}")
            docker_volumes = self.list_docker_volumes()
            base_dir = os.path.dirname(docker_compose_file)
            compose_data = self.read_docker_compose(docker_compose_file)
            real_volume_names = self.get_real_volume_names(
                compose_data, base_dir, docker_volumes
            )

            logger.info("Real volume names identified for backup: " + ", ".join(real_volume_names))

            backup_zip_path = self.backup_volumes_to_zip(
                base_dir, real_volume_names
            )

            if self.backup_successful:
                self.rclone_upload(
                    backup_zip_path,
                    os.path.basename(base_dir),
                    datetime.now().strftime("%Y%m%d%H%M%S"),
                )
                logger.info("Backup successfully uploaded.")
            else:
                self.notify_failure()

            self.cleanup(base_dir, real_volume_names)
            logger.info("Backup process completed.")

        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
            self.backup_successful = False
            self.notify_failure()
            sys.exit(1)

        if not self.backup_successful:
            sys.exit(1)


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
                elif volume_name.startswith(".") or not volume_name.endswith(
                    "/"
                ):
                    logger.info(f"skipping : {volume_name}")
                    continue
                elif os.path.isabs(volume_name):
                    volume_name = self.normalize_path(
                        os.path.join(base_dir, volume_name)
                    )
                if volume_name not in real_volume_names:
                    real_volume_names.append(volume_name)
                    logger.info(f"{volume_name} for {service_name} appended")
        return real_volume_names


if __name__ == "__main__":
    if len(sys.argv) != 2:
        logger.error("Usage: backup.py <path_to_docker_compose_file>")
        sys.exit(1)

    docker_compose_file = sys.argv[1]
    backup = DockerBackup()
    backup.main(docker_compose_file)
    if not backup.backup_successful:
        sys.exit(1)
