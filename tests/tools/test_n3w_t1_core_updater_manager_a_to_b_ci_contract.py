from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "n3w-t1-core-updater-manager-a-to-b-ci.yml"


def test_exact_artifact_id_downloads_use_rest_api_binding() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")

    assert source.count("uses: actions/download-artifact@v4") >= 3
    assert source.count("github-token: ${{ github.token }}") >= 3
    assert source.count("repository: ${{ github.repository }}") >= 3
    assert source.count("run-id: ${{ github.run_id }}") >= 2

    exact_manager = source.index("Re-download and verify Manager-only V2 package")
    pre_u1 = source.index("Download exact V2 Manager-only package from this run")

    exact_block = source[exact_manager:pre_u1]
    assert "artifact-ids: ${{ steps.upload.outputs.artifact-id }}" in exact_block
    assert "github-token: ${{ github.token }}" in exact_block
    assert "repository: ${{ github.repository }}" in exact_block
    assert "run-id: ${{ github.run_id }}" in exact_block

    pre_u1_block = source[pre_u1:]
    assert "artifact-ids: ${{ env.U1_MANAGER_PACKAGE_ARTIFACT_ID }}" in pre_u1_block
    assert "github-token: ${{ github.token }}" in pre_u1_block
    assert "repository: ${{ github.repository }}" in pre_u1_block
    assert "run-id: ${{ github.run_id }}" in pre_u1_block


def test_workflow_keeps_exact_artifact_id_authority() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "name: ${{ env.PACKAGE_NAME }}" not in source[source.index(
        "Re-download and verify Manager-only V2 package"
    ):source.index("Close exact V2 package binding")]
    assert "artifact-ids: ${{ steps.upload.outputs.artifact-id }}" in source
    assert "PACKAGE_ARTIFACT_ID: ${{ steps.upload.outputs.artifact-id }}" in source
