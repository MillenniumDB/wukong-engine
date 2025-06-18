import shutil
import subprocess
import threading
import time
from pathlib import Path

import psutil

# TODO: Refactor everything in this module later

# Config
mdb_root_path = Path('./../graph_databases/MillenniumDB-Dev')
import_file_destination_path = mdb_root_path / 'data'


class MillenniumDBServerManager:
    """
    Manages the MillenniumDB server.
    Make sure to configure the mdb_root_path variable.
    """

    server_started = False
    process: subprocess.Popen[bytes] = {}
    run_console = True

    def handle_output(self):
        """
        Handles the output console of the MillenniumDB server.
        When the console says that the server is listening, the server_started flag is set to True.
        """
        for line in self.process.stdout:
            line_str = line.decode().strip()
            print(line.decode().strip())
            if 'MillenniumDB HTTP/WebSocket server listening on' in line_str:
                self.server_started = True
                break
            if not self.run_console:
                break

    def __init__(self, data_name):
        self.data_name = data_name
        self.file_name = f'{self.data_name}_millenniumdb_db'

    def start_millenniumdb_server(self, timeout=60):
        "Starts the MillenniumDB server."
        command = ['build/Release/bin/mdb', 'server', f'dbs/{self.data_name}', '--no-browser']

        self.process = subprocess.Popen(command, cwd=mdb_root_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        output_thread = threading.Thread(target=self.handle_output)
        output_thread.start()

        timeout_counter = 0
        while not self.server_started:
            time.sleep(1)
            timeout_counter += 1
            if timeout_counter > timeout:
                print('MillenniumDB server failed to start in time. Terminating process.')
                self.run_console = False
                self.stop_millenniumdb_server()

                raise Exception('MillenniumDB server failed to start in time.')

    def stop_millenniumdb_server(self):
        "Stops the MillenniumDB server."
        print('Stopping MillenniumDB server...')
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

    def load_data(self, import_file_source_path):
        "Loads data to the MillenniumDB server."
        import_file_source = import_file_source_path / f'{self.file_name}.qm'
        import_file_destination = import_file_destination_path / f'{self.file_name}.qm'

        if import_file_destination.exists():
            import_file_destination.unlink()
        shutil.rmtree(import_file_destination_path / self.data_name, ignore_errors=True)
        shutil.copy2(str(import_file_source), str(import_file_destination))

        command = ['build/Release/bin/mdb', 'import', f'data/{self.file_name}.qm', f'dbs/{self.data_name}']

        result = subprocess.run(command, cwd=mdb_root_path, capture_output=True, text=True)
        print(f'Command: {command}')
        print(f'Return code: {result.returncode}')
        print(f'Output:\n{result.stdout}')
        print(f'Errors:\n{result.stderr}')


"""
# Config
#mdb_uri = "http://localhost:1234"

def parse_results(response: str):
    "Parse the response from MillenniumDB, removing the 'id' prefixes and quotes"
    lines = response.strip().split('\n')

    parsed_results = []
    for line in lines[1:]:
        items = line.split(',')
        mapped_items = []
        for item in items:
            if item.startswith('"'):
                mapped_items.append(item[1:-1])
            elif item.startswith('id'):
                mapped_items.append(int(item[2:]))
            else:
                mapped_items.append(item)
        parsed_results.append(mapped_items)

    return parsed_results

def clean_graph():
    ""
    Clean the graph with the MillenniumDB queries.
    ""
    pass
"""
