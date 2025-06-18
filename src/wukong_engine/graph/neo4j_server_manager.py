import subprocess
import threading
import time
from pathlib import Path

import psutil

from .load_data_to_neo4j import entities_to_csv, relations_to_csv

# TODO: Refactor everything in this module later

# Config
neo4j_bin_path = Path('./../graph_databases/neo4j-community-5.26.5/bin/')  # Linux standalone Neo4j community version
neo4j_admin_path = neo4j_bin_path / 'neo4j-admin'


class Neo4jServerManager:
    """
    Manages the Neo4j server.
    Make sure to configure the neo4j_bin_path variable.
    """

    server_started = False
    process: subprocess.Popen[bytes] = {}
    run_console = True

    def handle_output(self):
        """
        Handles the output console of the Neo4j server.
        When the console says that the server is listening, the server_started flag is set to True.
        """
        for line in self.process.stdout:
            line_str = line.decode().strip()
            print(line.decode().strip())
            if 'INFO  Started.' in line_str:
                self.server_started = True
                break
            if not self.run_console:
                break

    def start_server(self, timeout=60):
        """
        Starts the Neo4j server.

        Args:
            timeout (int, optional): The number of seconds to wait for the server to start. Defaults to 60.

        Raises:
            Exception: If the server fails to start within the given timeout.
        """

        command = ['./neo4j', 'console']

        self.process = subprocess.Popen(command, cwd=neo4j_bin_path, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        output_thread = threading.Thread(target=self.handle_output)
        output_thread.start()

        timeout_counter = 0
        while not self.server_started:
            time.sleep(1)
            timeout_counter += 1
            if timeout_counter > timeout:
                print('Neo4j server failed to start in time. Terminating process.')
                self.run_console = False
                self.stop_server()

                raise Exception('Neo4j server failed to start in time.')

    def stop_server(self):
        "Stops the Neo4j server."
        print('Stopping Neo4j server...')
        self.run_console = False

        try:
            pobj = psutil.Process(self.process.pid)
            for c in pobj.children(recursive=True):
                try:
                    c.terminate()
                    c.wait()
                except psutil.NoSuchProcess:
                    pass
            try:
                self.process.terminate()
                self.process.wait()
            except psutil.NoSuchProcess:
                pass
        except Exception:
            pass

    def load_data(
        self,
        entities_data: list[dict[str, str]],
        relations_data: list[dict[str, str]],
        results_path: Path,
    ):
        """
        Loads data from the given entities and relations into the Neo4j server.

        Args:
            entities_data (list[dict[str, str]]): A list of dictionaries containing the name and label of each entity type.
            relations_data (list[dict[str, str]]): A list of dictionaries containing the name, origin and target types and label of each relation type.
            results_path (Path): The path where the data will be stored.
        """
        entities_path = results_path / 'entities/'
        relations_path = results_path / 'relations/'

        elementIdToIdMaps = {}
        start_id = 1
        for entity_data in entities_data:
            json_file_name = entities_path / f'{entity_data["entity_name"]}.json'
            csv_file_name = entities_path / f'{entity_data["entity_name"]}.csv'

            start_id, elementIdToIdMap = entities_to_csv(json_file_name, csv_file_name, entity_data, start_id)
            elementIdToIdMaps[entity_data['entity_name']] = elementIdToIdMap

        for relation_data in relations_data:
            json_file_name = relations_path / f'{relation_data["relation_name"]}.json'
            csv_file_name = relations_path / f'{relation_data["relation_name"]}.csv'

            origin_id_mapping = elementIdToIdMaps[relation_data['origin_type']]
            target_id_mapping = elementIdToIdMaps[relation_data['target_type']]

            relations_to_csv(
                json_file_name,
                csv_file_name,
                relation_data,
                origin_id_mapping,
                target_id_mapping,
            )

        command = [str(neo4j_admin_path), 'database', 'import', 'full']

        for entity_data in entities_data:
            csv_file_name = entities_path / f'{entity_data["entity_name"]}.csv'
            flag = f'--nodes={csv_file_name.absolute()}'
            command += [flag]

        for relation_data in relations_data:
            csv_file_name = relations_path / f'{relation_data["relation_name"]}.csv'
            flag = f'--relationships={csv_file_name.absolute()}'
            command += [flag]

        delimeter1 = ';'
        delimeter2 = ','
        command += ['--overwrite-destination']
        command += [f'--array-delimiter={delimeter1}']
        command += [f'--delimiter={delimeter2}']
        command += ['--verbose']

        print('\nExecuting command: \n', command)

        try:
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            print('Command executed successfully')
            print('Output:\n', result.stdout)
        except subprocess.CalledProcessError as e:
            print('Error occurred while executing the command')
            print('Error Output:\n', e.stderr)
