import yaml
import subprocess
import os
import shutil
from zipfile import ZipFile

def main():
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
        subprocess.run(f'docker run --rm --volume {real_volume_name}:/backup --volume {volume_dir}:/backup alpine tar czf /backup/{real_volume_name}.tar.gz /backup/', shell=True)
        
    # Zip the entire folder
    with ZipFile(f'{base_dir}/backup.zip', 'w') as zipf:
        for root, dirs, files in os.walk(base_dir):
            for file in files:
                zipf.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), base_dir))

if __name__ == "__main__":
    main()
