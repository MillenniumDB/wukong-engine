import csv
import json
import logging
from pathlib import Path

from neo4j import GraphDatabase, ManagedTransaction

# TODO: Refactor everything in this module later

# Config
uri = 'bolt://localhost:7687'
iteration_threshold = 20
driver = GraphDatabase.driver(uri, connection_timeout=60)

# Disable info logging for Neo4j
neo4j_log = logging.getLogger('neo4j')
neo4j_log.setLevel(logging.CRITICAL)


# TODO: Only call this when stated by the user
def clean_graph():
    """
    Applies optional (user selected) graph cleaning operations:

    1. Remove loops within a specified relation (maybe a custom query?).
    2. Remove redundant edges for transitive relations (decide if this should be in custom queries instead).
    3. Merge duplicate nodes and edges (this is probably a custom query, since we already do a general version in information_extraction).
    """

    print('Cleaning graph...')
    """
    with GraphDatabase.driver(uri) as driver:
        with driver.session() as session:
            session.execute_write(remove_wrong_edges)
    """


# TODO: Modify to apply a custom query set to manipulate the graph
def run_custom_queries(custom_queries_data: list):
    """
    Applies multiple custom queries.
    These are used for graph cleaning and manipulation.
    """

    queries_records = []
    with GraphDatabase.driver(uri) as driver:
        with driver.session() as session:
            for query_data in custom_queries_data:
                custom_query = query_data['custom_query']
                parameters = query_data.get('parameters', None)
                results = session.run(custom_query, parameters=parameters)
                records = [result for result in results]
                queries_records.append(records)

    return queries_records


# TODO: Modify to apply a custom query to manipulate the graph
def run_custom_query(custom_query: str, parameters: dict = None):
    """
    Applies a single custom query.
    """

    with GraphDatabase.driver(uri) as driver:
        with driver.session() as session:
            results = session.run(custom_query, parameters=parameters)
            records = [result for result in results]

    return records


# TODO: Check later if this is needed
def merge_edges(tx, edge1, edge2, labels: list[str] = []):
    """
    Combina dos aristas y les agrega las etiquetas si las hubiera.
    IMPORTANTE: Solo mantiene las propiedades de una arista.
    Existe el método apoc.refactor.mergeRelationships para combinar aristas, pero está buggeado
    """

    set_labels = ''
    if labels:
        set_labels = ':'.join(labels)
    merge_query = f"""
        MATCH (start)-[edge1]->(end),
            (start)-[edge2]->(end)
        WHERE elementid(edge1) = $edge1_id AND elementid(edge2) = $edge2_id
        CREATE (start)-[mergedEdge:{set_labels}]->(end)
        SET mergedEdge += edge1,
            mergedEdge += edge2
        DELETE edge1, edge2
        RETURN start, end, mergedEdge
    """
    tx.run(merge_query, edge1_id=edge1.element_id, edge2_id=edge2.element_id)


# TODO: Check later if this is needed
def merge_node_bulk(merge_list: list):
    """
    Realiza un conjunto de combinaciones de nodos en una sola transacción
    """

    with GraphDatabase.driver(uri) as driver:
        with driver.session() as session:
            for merge in merge_list:
                node1 = merge['node1']
                node2 = merge['node2']
                labels = merge.get('labels', [])
                session.execute_write(merge_nodes_with_tx, node1, node2, labels=labels)


# TODO: Check later if this is needed
def merge_nodes(node1, node2, labels: list[str] = []):
    """
    Combina dos nodos y les agrega las etiquetas si las hubiera
    """

    with GraphDatabase.driver(uri) as driver:
        with driver.session() as session:
            session.execute_write(merge_nodes_with_tx, node1, node2, labels=labels)


# TODO: Check later if this is needed
def merge_nodes_with_tx(tx: ManagedTransaction, node1, node2, labels: list[str] = []):
    """
    Combina dos nodos y les agrega las etiquetas si las hubiera
    """

    discard_properties = []
    for key in node1.keys():
        if key in node2.keys() and isinstance(node1[key], list) and isinstance(node2[key], list):
            if not node1[key] and not node2[key]:
                discard_properties.append(key)

    if discard_properties:
        discard_properties_str = ', '.join([f"{prop}:'discard'" for prop in discard_properties])
        properties_str = f"{{ {discard_properties_str}, `.*`: 'combine' }}"
    else:
        properties_str = "'combine'"

    set_labels = ''
    if labels:
        set_labels = 'SET node:' + ':'.join(labels)
    merge_query = f"""
        MATCH (node1), (node2)
        WHERE elementid(node1) = $node1_id AND elementid(node2) = $node2_id
        CALL apoc.refactor.mergeNodes([node1, node2], {{ properties: {properties_str}, mergeRels: true, singleElementAsArray: true, produceSelfRel: false }})
        YIELD node
        {set_labels}
        RETURN node
    """
    tx.run(merge_query, node1_id=node1.element_id, node2_id=node2.element_id)


def export_to_millenniumdb(file_name: Path):
    """
    Export the graph to the MillenniumDB format.
    """

    def custom_repr(value):
        if isinstance(value, str):
            return f'"{value.replace('"', "")}"'
        elif isinstance(value, list):
            return f'"{",".join(str(v).replace('"', "") for v in value)}"'
        return repr(value)

    with GraphDatabase.driver(uri) as driver:
        with driver.session() as session:
            nodes_query = 'MATCH (n) RETURN n'
            edges_query = 'MATCH ()-[r]->() RETURN r'

            nodes = session.run(nodes_query)
            edges = session.run(edges_query)

            millenniumdb_file = f'{file_name}.qm'

            with open(millenniumdb_file, 'w', encoding='utf-8') as mf:
                for record in nodes:
                    node = record['n']
                    node_id = f'id{node.id}'
                    labels = ':'.join(node.labels)
                    properties = ' '.join(f'{k}:{custom_repr(v)}' for k, v in node.items())
                    mf.write(f'{node_id} :{labels} {properties}\n')

                for record in edges:
                    edge = record['r']
                    start_id = f'id{edge.start_node.id}'
                    end_id = f'id{edge.end_node.id}'
                    type_ = edge.type
                    properties = ' '.join(f'{k}:{custom_repr(v)}' for k, v in edge.items())
                    mf.write(f'{start_id}->{end_id} :{type_} {properties}\n')


def export_to_json(output_dir: Path):
    """
    Export the graph to JSON files based on entity and relation types.
    """

    def save_to_file(data, file_name):
        with open(output_dir / file_name, 'w') as f:
            json.dump(data, f, indent=4)

    with GraphDatabase.driver(uri) as driver:
        with driver.session() as session:
            nodes_query = 'MATCH (n) RETURN n'
            edges_query = 'MATCH ()-[r]->() RETURN r'

            nodes = session.run(nodes_query)
            edges = session.run(edges_query)

            node_data = {}
            edge_data = {}

            for record in nodes:
                node = record['n']
                node_type = list(node.labels)[0].lower()
                node_info = {'id': node.id, 'properties': dict(node)}

                if node_type not in node_data:
                    node_data[node_type] = []
                node_data[node_type].append(node_info)

            for record in edges:
                edge = record['r']
                edge_type = edge.type.lower()
                edge_info = {
                    'id': edge.id,
                    'properties': dict(edge),
                    'start_node_id': edge.start_node.id,
                    'end_node_id': edge.end_node.id,
                }

                if edge_type not in edge_data:
                    edge_data[edge_type] = []
                edge_data[edge_type].append(edge_info)

            for node_type, data in node_data.items():
                save_to_file(data, f'{node_type}.json')

            for edge_type, data in edge_data.items():
                save_to_file(data, f'{edge_type}.json')


def entities_to_csv(json_file, csv_file, entity_data, start_id=1):
    """
    Convert entities from JSON to CSV.
    It adds an id to each entity and returns the next id.
    Adds a :LABEL column to specify the type of entity.
    """

    entity_label = entity_data['entity_label']
    elementIdToIdMap = {}

    with open(json_file, 'r') as f:
        entities = json.load(f)

    current_id = start_id

    headers = set()
    for entity in entities:
        entity['_referencedInDocument:int[]'] = entity['_referencedInDocument']
        del entity['_referencedInDocument']

        entity['origin_reference:string[]'] = entity['origin_reference']
        del entity['origin_reference']

        headers.update(entity.keys())
        entity['id:ID'] = current_id

        elementIdToIdMap[entity[f'{entity_data["entity_name"]}Id']] = current_id
        current_id += 1

    headers = sorted(headers)

    headers.insert(0, 'id:ID')
    headers.insert(0, ':LABEL')

    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()

        for entity in entities:
            if '_referencedInDocument:int[]' in entity:
                entity['_referencedInDocument:int[]'] = list(
                    set([ref['documentId'] for ref in entity['_referencedInDocument:int[]']])
                )
                entity['_referencedInDocument:int[]'] = ';'.join(
                    str(documentId) for documentId in entity['_referencedInDocument:int[]']
                )

            if 'origin_reference:string[]' in entity:
                entity['origin_reference:string[]'] = ';'.join(entity['origin_reference:string[]'])

            entity[':LABEL'] = entity_label

            row = {field: entity.get(field, '') for field in headers}

            writer.writerow(row)

    return current_id, elementIdToIdMap


def relations_to_csv(
    json_file, csv_file, relation_data, origin_id_mapping: dict[int, int], target_id_mapping: dict[int, int]
):
    """
    Convert relations from JSON to CSV.
    Adds columns for :START_ID, :END_ID, :TYPE, and any relationship properties.
    """

    relation_label = relation_data['relation_label']

    with open(json_file, 'r') as f:
        relations = json.load(f)

    headers = set()
    for relation in relations:
        relation['_referencedInDocument:int[]'] = relation['_referencedInDocument']
        del relation['_referencedInDocument']

        relation['origin_reference:string[]'] = relation['origin_reference']
        del relation['origin_reference']

        headers.update(relation.keys())

    headers = sorted(headers)

    headers.insert(0, ':START_ID')
    headers.insert(1, ':END_ID')
    headers.insert(2, ':TYPE')

    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()

        for relation in relations:
            origin_id = relation[f'{relation_data["relation_origin_attribute_name"]}']
            start_id = origin_id_mapping[origin_id]

            target_id = relation[f'{relation_data["relation_target_attribute_name"]}']
            end_id = target_id_mapping[target_id]

            if '_referencedInDocument:int[]' in relation:
                relation['_referencedInDocument:int[]'] = list(
                    set([ref['documentId'] for ref in relation['_referencedInDocument:int[]']])
                )
                relation['_referencedInDocument:int[]'] = ';'.join(
                    str(documentId) for documentId in relation['_referencedInDocument:int[]']
                )

            if 'origin_reference:string[]' in relation:
                relation['origin_reference:string[]'] = ';'.join(relation['origin_reference:string[]'])

            relation[':START_ID'] = start_id
            relation[':END_ID'] = end_id
            relation[':TYPE'] = relation_label

            row = {field: relation.get(field, '') for field in headers}

            writer.writerow(row)
