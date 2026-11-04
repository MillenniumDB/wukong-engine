"""Tests for the creation of new workspaces with skeleton input files."""

from pathlib import Path

import pytest

from wukong_engine.app.workspace import Workspace, WorkspaceValidator
from wukong_engine.app.workspace.exceptions import WorkspaceError
from wukong_engine.infrastructure.definitions.documents import LocalDocumentRegistryProvider
from wukong_engine.infrastructure.definitions.knowledge import LocalKnowledgeModelProvider
from wukong_engine.infrastructure.storage.filesystem import LocalWorkspaceInitializer


def test_a_new_workspace_has_valid_input_files_full_of_placeholders(tmp_path: Path) -> None:
    """Create a valid workspace whose files load as they are, with placeholders marking what to edit."""
    workspace = Workspace(root=tmp_path / 'new' / 'workspace')

    registry_path, model_path = LocalWorkspaceInitializer().initialize(workspace)

    WorkspaceValidator().validate(workspace=workspace)
    registry = LocalDocumentRegistryProvider().get(str(registry_path), str(tmp_path))
    model = LocalKnowledgeModelProvider().get(str(model_path))
    assert [str(name) for name in registry.collections] == ['my-documents']
    assert [str(name) for name in model.active_entity_types] == ['Organization']
    assert '<' in model_path.read_text(encoding='utf-8')
    assert '<' in registry_path.read_text(encoding='utf-8')


def test_existing_input_files_are_never_overwritten(tmp_path: Path) -> None:
    """Refuse to create a workspace over an existing input file, writing nothing."""
    workspace = Workspace(root=tmp_path)
    workspace.paths.knowledge_model.write_text('{"entity_types": {}}', encoding='utf-8')

    with pytest.raises(WorkspaceError, match=r'already has knowledge_model\.json'):
        LocalWorkspaceInitializer().initialize(workspace)

    assert workspace.paths.knowledge_model.read_text(encoding='utf-8') == '{"entity_types": {}}'
    assert not workspace.paths.document_registry.exists()
