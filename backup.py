import os
import sys
import yaml
import subprocess
import logging
from zipfile import ZipFile
from socket import gethostname
import requests
from datetime import datetime

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)


class DockerBackup:
    """Class for performing Docker backups."""

    def __init__(self):
        self.remote_name = os.getenv("RCLONE_REMOTE_NAME")
        logger.info(f"Variable found RCLONE_REMOTE_NAME:{self.remote_name}")
        self.remote_folder = os.getenv("RCLONE_REMOTE_FOLDER")
        logger.info(f"Variable found RCLONE_REMOTE_FOLDER:{self.remote_folder}")
        self.fail_notify_url = os.getenv("FAIL_NOTIFY_URL")
        logger.info(f"Variable found FAIL_NOTIFY_URL:{self.fail_notify_url}")
        self.validate_and_notify_env_vars()

    def execute_command(self, command):
        """Execute shell command."""
        try:
            subprocess.run(
                command, shell=True, check=True, stdout=sys.stdout, stderr=sys.stderr
            )
        except subprocess.CalledProcessError as exc:
            self.notify_failure()
            logger.error(f"Error: {exc}")
            sys.exit(1)

    def notify_failure(self):
        """Notify failure through a URL."""
        if self.fail_notify_url:
            try:
                requests.post(
                    self.fail_notify_url, json={"message": "Backup process failed."}
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
                logger.error(f"Failed to fetch docker volumes: {e}")
                sys.exit(1)
        return real_volume_names

    def backup_volumes_to_zip(self, base_dir, real_volume_names):
        zip_file_path = f"{base_dir}/backup.zip"
        with ZipFile(zip_file_path, "w") as zipf:
            for root, _, files in os.walk(base_dir):
                for file in files:
                    full_path = os.path.join(root, file)
                    if full_path == zip_file_path:
                        continue
                    zipf.write(
                        full_path,
                        os.path.relpath(full_path, base_dir),
                    )
        return zip_file_path

    def rclone_upload(self, file_path, parent_folder_name, suffix):
        hostname = get_hostname()
        remote_path = (
            f"{self.remote_name}:/{self.remote_folder}/{hostname}/{parent_folder_name}/"
        )
        remote_old_path = f"{self.remote_name}:/{self.remote_folder}/old/{hostname}/{parent_folder_name}/"
        self.execute_command(
            f"rclone sync --progress {file_path} {remote_path} --backup-dir {remote_old_path} --suffix {suffix} --suffix-keep-extension"
        )

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
                    f"docker run --rm --volume {real_volume_name}:/backup --volume {volume_dir}:/backup_dir ubuntu tar czfP /backup_dir/{real_volume_name}.tar.gz -C / /backup/"
                )

            zip_file_path = self.backup_volumes_to_zip(base_dir, real_volume_names)

            self.rclone_upload(zip_file_path, parent_folder_name, suffix)

            self.cleanup(base_dir, volume_names)
            logging.info("Backup completed successfully.")
        except Exception as e:
            logger.error(f"Backup process failed: {e}")
            self.notify_failure()
            sys.exit(1)


def get_hostname() -> str:
    """Retrieve the hostname."""
    try:
        with open("/etc/host_hostname", "r") as file:
            hostname = file.read().strip()
    except FileNotFoundError:
        hostname = gethostname()
    return hostname


if __name__ == "__main__":
    DOCKER_COMPOSE_FILE = sys.argv[1]
    BACKUP = DockerBackup()
    BACKUP.main(DOCKER_COMPOSE_FILE)
